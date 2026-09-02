"""Contract tests for the WhatsApp/GOWA notifications in the Debian daily runner.

The runner is a bash script, so these tests execute the real
``scripts/run_daily_report.sh`` inside a temporary application layout with a stub
interpreter, a stub ``xvfb-run`` and a local HTTP stub standing in for the GOWA
REST gateway. That keeps the production command contract (H-1, ``--targets ocr``,
``--report-mode ocr``, ``xvfb-run``) and the real ``curl`` request under test while
never contacting a real gateway or the private ``config/.env``.
"""

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_daily_report.sh"
YESTERDAY = (date.today() - timedelta(days=1)).strftime("%Y%m%d")
GROUP_JID = "1234567890-placeholder@g.us"
SECRET_DEVICE_ID = "device-secret-placeholder"
DEFAULT_GATEWAY_PORT = 3000

STUB_PYTHON = """#!/usr/bin/env bash
if [ "${1:-}" = "-c" ]; then
  exec "${TEST_PYTHON}" "$@"
fi
printf '%s\\n' "$@" >> "$PIPELINE_LOG"
printf '\\n' >> "$PIPELINE_LOG"
if [ -n "${PIPELINE_NOISE:-}" ]; then
  printf '%s\\n' "$PIPELINE_NOISE"
  printf '%s\\n' "$PIPELINE_NOISE" >&2
fi
exit "${PIPELINE_CODE:-0}"
"""

STUB_XVFB_RUN = """#!/usr/bin/env bash
printf '%s\\n' "$@" >> "$XVFB_LOG"
printf '\\n' >> "$XVFB_LOG"
shift
exec "$@"
"""

EXPECTED_PIPELINE_ARGV = [
    "-m",
    "mrtg_automation",
    "full",
    "--date",
    YESTERDAY,
    "--targets",
    "ocr",
    "--report-mode",
    "ocr",
]


class GatewayState(SimpleNamespace):
    requests: list[dict[str, Any]]
    status: int
    delay: float
    url: str


def _write_stub(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8", newline="\n")
    path.chmod(0o755)


def _records(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    blocks = path.read_text(encoding="utf-8").split("\n\n")
    return [block.split("\n") for block in blocks if block]


def _bash_executable() -> str | None:
    """Return a POSIX bash that actually runs, or ``None`` when unavailable.

    ``shutil.which("bash")`` can resolve the Windows WSL relay stub, which hangs or
    fails without an installed distribution, so every candidate is probed.
    """
    candidates = [os.environ.get("MRTGTEST_BASH"), shutil.which("bash")]
    candidates += [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
    ]
    for candidate in candidates:
        if not candidate or not Path(candidate).exists():
            continue
        try:
            probe = subprocess.run(
                [candidate, "-c", "printf ok"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if probe.returncode == 0 and probe.stdout.strip() == "ok":
            return candidate
    return None


def _handler_for(state: GatewayState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            state.requests.append({"path": self.path, "headers": dict(self.headers), "body": body})
            if state.delay:
                time.sleep(state.delay)
            self.send_response(state.status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, *args: Any) -> None:
            return

    return Handler


def _serve(state: GatewayState, port: int) -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = ThreadingHTTPServer(("127.0.0.1", port), _handler_for(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


@pytest.fixture(scope="session")
def bash() -> str:
    executable = _bash_executable()
    if not executable:
        pytest.skip("a working POSIX bash is required to exercise the runner script")
    return executable


@pytest.fixture
def gateway() -> Iterator[GatewayState]:
    """Local HTTP stub that records what the runner POSTs to the GOWA gateway."""
    state = GatewayState(requests=[], status=200, delay=0.0, url="")
    server, thread = _serve(state, 0)
    state.url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)


@pytest.fixture
def runner(
    bash: str, gateway: GatewayState, tmp_path: Path
) -> Callable[..., tuple[subprocess.CompletedProcess, dict[str, Any]]]:
    app = tmp_path / "app"
    (app / "scripts").mkdir(parents=True)
    (app / "config").mkdir()
    (app / ".venv" / "bin").mkdir(parents=True)
    shutil.copy2(SCRIPT, app / "scripts" / SCRIPT.name)

    _write_stub(app / ".venv" / "bin" / "python", STUB_PYTHON)

    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    _write_stub(stub_bin / "xvfb-run", STUB_XVFB_RUN)

    pipeline_log = tmp_path / "pipeline.log"
    xvfb_log = tmp_path / "xvfb.log"

    env = os.environ.copy()
    env.update(
        PATH=f"{stub_bin}{os.pathsep}{env.get('PATH', '')}",
        PIPELINE_LOG=pipeline_log.as_posix(),
        XVFB_LOG=xvfb_log.as_posix(),
        TEST_PYTHON=Path(sys.executable).as_posix(),
        DISPLAY=":0",
    )
    for leaked in (
        "WA_ALERT_ENABLED",
        "WA_GATEWAY_URL",
        "WA_DEVICE_ID",
        "WA_TARGET_JID",
        "PIPELINE_CODE",
        "PIPELINE_NOISE",
    ):
        env.pop(leaked, None)

    resolved_xvfb = subprocess.run(
        [bash, "-c", "command -v xvfb-run"],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    ).stdout.strip()
    # MSYS rewrites the temporary path, so only the pytest directory name is compared.
    xvfb_stub_active = tmp_path.name in resolved_xvfb

    def run(
        config: str | None = None, *, xvfb: bool = True, **extra: str
    ) -> tuple[subprocess.CompletedProcess, dict[str, Any]]:
        env_file = app / "config" / ".env"
        if config is None:
            env_file.unlink(missing_ok=True)
        else:
            env_file.write_text(config, encoding="utf-8", newline="\n")
        if not xvfb:
            (stub_bin / "xvfb-run").unlink(missing_ok=True)
        env.update(extra)

        result = subprocess.run(
            [bash, (app / "scripts" / SCRIPT.name).as_posix()],
            cwd=app,
            env=env,
            text=True,
            capture_output=True,
            timeout=180,
        )
        observed = {
            "pipeline": _records(pipeline_log),
            "xvfb": _records(xvfb_log),
            "xvfb_stub_active": xvfb_stub_active,
        }
        for log in (pipeline_log, xvfb_log):
            log.unlink(missing_ok=True)
        return result, observed

    return run


def _messages(requests: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [json.loads(request["body"]) for request in requests]


def _enabled_config(extra: str = "") -> str:
    return f"WA_ALERT_ENABLED=true\nWA_TARGET_JID={GROUP_JID}\n{extra}"


def test_disabled_configuration_sends_nothing(runner, gateway):
    result, _ = runner(f"WA_ALERT_ENABLED=false\nWA_TARGET_JID={GROUP_JID}\n")
    assert result.returncode == 0
    assert gateway.requests == []


def test_missing_configuration_is_nonfatal(runner, gateway):
    result, _ = runner(None)
    assert result.returncode == 0
    assert gateway.requests == []


def test_enabled_without_target_group_is_silent(runner, gateway):
    result, _ = runner("WA_ALERT_ENABLED=true\n")
    assert result.returncode == 0
    assert gateway.requests == []


def test_start_then_success_payload_hits_send_message(runner, gateway):
    result, _ = runner(
        _enabled_config(f"WA_DEVICE_ID={SECRET_DEVICE_ID}\nWA_GATEWAY_URL={gateway.url}\n")
    )
    assert result.returncode == 0
    assert len(gateway.requests) == 2
    assert all(request["path"] == "/send/message" for request in gateway.requests)
    assert all(
        request["headers"]["X-Device-Id"] == SECRET_DEVICE_ID for request in gateway.requests
    )
    assert all(
        request["headers"]["Content-Type"].startswith("application/json")
        for request in gateway.requests
    )
    assert [message["message"] for message in _messages(gateway.requests)] == [
        f"MRTG TelkomCare daily report: STARTED (date {YESTERDAY}).",
        f"MRTG TelkomCare daily report: SUCCESS (date {YESTERDAY}).",
    ]
    assert all(message["phone"] == GROUP_JID for message in _messages(gateway.requests))


def test_device_header_omitted_when_not_configured(runner, gateway):
    result, _ = runner(_enabled_config(f"WA_GATEWAY_URL={gateway.url}\n"))
    assert result.returncode == 0
    assert len(gateway.requests) == 2
    assert all("X-Device-Id" not in request["headers"] for request in gateway.requests)


@pytest.mark.parametrize("extra", ["", "WA_GATEWAY_URL=\n", 'WA_GATEWAY_URL="  "\n'])
def test_default_gateway_is_localhost_3000(runner, extra):
    """The documented default is exercised by binding the real localhost port."""
    state = GatewayState(requests=[], status=200, delay=0.0, url="")
    try:
        server, thread = _serve(state, DEFAULT_GATEWAY_PORT)
    except OSError:
        pytest.skip(f"localhost:{DEFAULT_GATEWAY_PORT} is already in use")
    try:
        result, _ = runner(_enabled_config(extra))
        assert result.returncode == 0
        assert len(state.requests) == 2
        assert all(request["path"] == "/send/message" for request in state.requests)
        assert [message["message"] for message in _messages(state.requests)] == [
            f"MRTG TelkomCare daily report: STARTED (date {YESTERDAY}).",
            f"MRTG TelkomCare daily report: SUCCESS (date {YESTERDAY}).",
        ]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)


def test_quoted_and_aliased_env_values_are_honoured(runner, gateway):
    result, _ = runner(
        'export WA_ALERT_ENABLED="yes"\n'
        f'WA_TARGET_JID="{GROUP_JID}"\n'
        f'WA_GATEWAY_URL="{gateway.url}/"\n'
    )
    assert result.returncode == 0
    assert len(gateway.requests) == 2
    assert all(request["path"] == "/send/message" for request in gateway.requests)
    assert all(message["phone"] == GROUP_JID for message in _messages(gateway.requests))


def test_pipeline_failure_sends_failure_notice_and_preserves_exit_code(runner, gateway):
    result, _ = runner(
        _enabled_config(f"WA_GATEWAY_URL={gateway.url}\n"),
        PIPELINE_CODE="23",
    )
    assert result.returncode == 23
    assert [message["message"] for message in _messages(gateway.requests)] == [
        f"MRTG TelkomCare daily report: STARTED (date {YESTERDAY}).",
        f"MRTG TelkomCare daily report: FAILED (date {YESTERDAY}, exit code 23).",
    ]


def test_gateway_http_error_never_masks_pipeline_status(runner, gateway):
    gateway.status = 500
    result, _ = runner(
        _enabled_config(f"WA_GATEWAY_URL={gateway.url}\n"),
        PIPELINE_CODE="17",
    )
    assert result.returncode == 17
    assert len(gateway.requests) == 2
    assert "[WARNING] WhatsApp notification" in result.stderr
    assert "not delivered by GOWA gateway" in result.stderr


def test_gateway_timeout_never_masks_pipeline_status(runner, gateway):
    gateway.delay = 8  # longer than the runner's notification timeout
    result, _ = runner(
        _enabled_config(f"WA_GATEWAY_URL={gateway.url}\n"),
        PIPELINE_CODE="17",
    )
    assert result.returncode == 17
    assert len(gateway.requests) == 2
    assert "not delivered by GOWA gateway" in result.stderr


def test_gateway_unavailable_while_pipeline_succeeds(runner):
    result, _ = runner(
        _enabled_config("WA_GATEWAY_URL=http://127.0.0.1:1/\n"),
    )
    assert result.returncode == 0
    assert "[WARNING] WhatsApp notification" in result.stderr


def test_messages_never_leak_group_jid_device_id_or_pipeline_detail(runner, gateway):
    noise = "Traceback (most recent call last): RuntimeError token=sk-leak password=hunter2"
    result, _ = runner(
        _enabled_config(f"WA_GATEWAY_URL={gateway.url}\nWA_DEVICE_ID={SECRET_DEVICE_ID}\n"),
        PIPELINE_CODE="9",
        PIPELINE_NOISE=noise,
    )
    assert result.returncode == 9
    assert noise in result.stderr

    messages = _messages(gateway.requests)
    assert len(messages) == 2
    assert messages[-1]["message"] == (
        f"MRTG TelkomCare daily report: FAILED (date {YESTERDAY}, exit code 9)."
    )
    for leaked in ("sk-leak", "hunter2", "Traceback", "RuntimeError"):
        assert all(leaked not in message["message"] for message in messages)
    for secret in (GROUP_JID, SECRET_DEVICE_ID):
        assert secret not in result.stdout
        assert secret not in result.stderr


def test_daily_command_contract_is_preserved(runner):
    result, observed = runner(_enabled_config())
    assert result.returncode == 0
    assert observed["pipeline"] == [EXPECTED_PIPELINE_ARGV]
    if observed["xvfb_stub_active"]:
        xvfb_argv = observed["xvfb"][0]
        assert xvfb_argv[0] == "-a"
        assert xvfb_argv[1].endswith("/.venv/bin/python")
        assert xvfb_argv[2:] == EXPECTED_PIPELINE_ARGV


def test_pipeline_runs_without_xvfb_when_unavailable(runner):
    result, observed = runner(_enabled_config(), xvfb=False)
    if not observed["xvfb_stub_active"]:
        pytest.skip("a real xvfb-run wins the PATH lookup, so the fallback cannot be isolated")
    assert result.returncode == 0
    assert "xvfb-run not found" in result.stdout
    assert observed["xvfb"] == []
    assert observed["pipeline"] == [EXPECTED_PIPELINE_ARGV]
