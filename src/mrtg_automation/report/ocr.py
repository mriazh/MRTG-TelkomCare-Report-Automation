import contextlib
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

from mrtg_automation.config import Config
from mrtg_automation.report.gemini_ocr import GeminiLegendExtractor

logger = logging.getLogger("mrtg_automation.ocr")


@contextlib.contextmanager
def _silence_paddlex_teardown():
    """Capture PaddleX post-init teardown noise (Creating model ... lines)."""
    with open(os.devnull, "w") as devnull:
        with contextlib.redirect_stderr(devnull):
            yield


class _LazyGeminiExtractor:
    """Lazily construct the Gemini provider only when OCR needs it.

    Keeping this small proxy as the public collaborator attribute preserves the
    existing test/injection seam without initializing an optional network
    provider for confident PaddleOCR results.
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self._provider = None

    def extract_legend(self, image_path: Path) -> dict[str, Any]:
        if self._provider is None:
            self._provider = GeminiLegendExtractor(self.config)
        return self._provider.extract_legend(image_path)


class OCRExtractor:
    _engine = None

    def __init__(self, config: Config | None = None, gemini_extractor=None) -> None:
        self.config = config or Config()
        # Keep a single provider collaborator per OCR operation.  Besides making
        # the dependency injectable for deterministic tests, this preserves the
        # provider's per-operation model failure counters across OCR retries.
        self.gemini_extractor = (
            gemini_extractor if gemini_extractor is not None else _LazyGeminiExtractor(self.config)
        )

    def extract(
        self, image_path: Path, max_retries: int = 3, progress_callback=None
    ) -> dict[str, Any]:
        last_result = None
        for _attempt in range(max(1, max_retries)):
            try:
                res = self._perform_single_extract(
                    image_path,
                    self.config,
                    progress_callback=progress_callback,
                    gemini_extractor=self.gemini_extractor,
                )
            except (OSError, RuntimeError, ValueError, TypeError):
                logger.exception("OCR extraction failed")
                res = {
                    "values": {},
                    "engine_used": "Error",
                    "decision_reason": "both_unknown",
                    "paddle_confidence": 0.0,
                    "paddle_values": {},
                    "gemini_values": {},
                    "gemini_model": "",
                    "paddle_complete": False,
                    "gemini_complete": False,
                    "gemini_called": False,
                    "attempted_models": [],
                    "model_failures": {},
                    "attempts": 0,
                    "gemini_error_reason": "OCR_EXCEPTION",
                }
            last_result = res
            if res.get("gemini_complete") or res.get("paddle_complete"):
                break
        return last_result or {
            "values": {},
            "engine_used": "Paddle (Fallback)",
            "decision_reason": "both_incomplete",
            "paddle_confidence": 0.0,
            "paddle_values": {},
            "gemini_values": {},
            "gemini_model": "",
            "paddle_complete": False,
            "gemini_complete": False,
            "gemini_called": False,
            "attempted_models": [],
            "model_failures": {},
            "attempts": 0,
            "gemini_error_reason": "OCR_NO_RESULT",
        }

    @classmethod
    def extract_mrtg_values_with_metadata(
        cls,
        image_path: Path,
        config: Config = None,
        progress_callback=None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        return cls(config).extract(
            image_path,
            max_retries=max_retries,
            progress_callback=progress_callback,
        )

    @classmethod
    def _get_engine(cls):
        """Singleton: initialization of PaddleOCR with strict silence."""
        if cls._engine is None:
            # Set environment variables BEFORE importing paddle
            os.environ["GLOG_minloglevel"] = "3"
            os.environ["FLAGS_minloglevel"] = "3"
            os.environ["PADDLE_LOG_LEVEL"] = "ERROR"
            os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
            os.environ["PADDLEX_DISABLE_PRINT"] = "1"
            os.environ["FLAGS_enable_pir_api"] = "0"
            os.environ["FLAGS_enable_new_executor"] = "0"
            os.environ["FLAGS_use_onednn"] = "0"
            os.environ["FLAGS_use_mkldnn"] = "0"
            os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"
            os.environ["FLAGS_use_gpu"] = "0"
            os.environ["KMP_WARNINGS"] = "0"

            has_fd = False
            try:
                _stdout_fd = sys.stdout.fileno()
                _stderr_fd = sys.stderr.fileno()
                _save_stdout = os.dup(_stdout_fd)
                _save_stderr = os.dup(_stderr_fd)
                has_fd = True
            except Exception as e:
                logger.warning(f"Could not redirect stdout/stderr: {e}")

            try:
                import warnings

                warnings.filterwarnings("ignore")

                if has_fd:
                    fnull = open(os.devnull, "w")
                    os.dup2(fnull.fileno(), _stdout_fd)
                    os.dup2(fnull.fileno(), _stderr_fd)

                try:
                    import logging as py_logging

                    for _name in (
                        "paddlex",
                        "paddlex.inference",
                        "paddlex.utils",
                        "paddle",
                        "ppocr",
                    ):
                        py_logging.getLogger(_name).setLevel(py_logging.ERROR)
                        py_logging.getLogger(_name).propagate = False

                    with _silence_paddlex_teardown():
                        import paddle

                        paddle.enable_static()
                        from paddleocr import PaddleOCR

                        cls._engine = PaddleOCR(lang="en")
                except ImportError as e:
                    raise ImportError(
                        "OCR dependencies are not installed. Please run: pip install -e .[ocr]"
                    ) from e
                except Exception as e:
                    raise RuntimeError(
                        f"OCR Engine failed to initialize: {type(e).__name__}"
                    ) from e

            finally:
                if has_fd:
                    os.dup2(_save_stdout, _stdout_fd)
                    os.dup2(_save_stderr, _stderr_fd)
                    os.close(_save_stdout)
                    os.close(_save_stderr)
                    fnull.close()

            logger.debug("PaddleOCR engine initialized successfully.")

        return cls._engine

    @classmethod
    def _extract_paddle(cls, image_path: Path) -> dict[str, Any]:
        paddle_values = {}
        paddle_complete = False
        paddle_confidence = 0.0
        error_reason = None
        try:
            ocr = cls._get_engine()
            res_iter = None
            if hasattr(ocr, "predict"):
                res_iter = ocr.predict(str(image_path))
            elif hasattr(ocr, "ocr"):
                res_iter = ocr.ocr(str(image_path))

            all_texts, all_confs = [], []
            if res_iter:
                for res in res_iter:
                    data = res.get("res", res) if isinstance(res, dict) else res
                    if isinstance(data, dict):
                        if "rec_texts" in data:
                            all_texts.extend([str(t).strip() for t in data["rec_texts"]])
                            if "rec_scores" in data:
                                try:
                                    all_confs.extend([float(s) for s in data["rec_scores"]])
                                except (TypeError, ValueError):
                                    pass
                        elif "text" in data:
                            all_texts.append(str(data["text"]).strip())
                            if "confidence" in data:
                                try:
                                    all_confs.append(float(data["confidence"]))
                                except (TypeError, ValueError):
                                    pass
                    elif isinstance(data, list):
                        for line in data:
                            if isinstance(line, list) and len(line) > 1:
                                all_texts.append(str(line[1][0]).strip())
                                try:
                                    all_confs.append(float(line[1][1]))
                                except (IndexError, TypeError, ValueError):
                                    pass
                            elif isinstance(line, dict) and "text" in line:
                                all_texts.append(str(line["text"]).strip())
                                if "confidence" in line:
                                    try:
                                        all_confs.append(float(line["confidence"]))
                                    except (TypeError, ValueError):
                                        pass

            if all_confs:
                paddle_confidence = sum(all_confs) / len(all_confs)

            def find_values_in_section(section_headers, texts):
                section_texts = []
                found = False
                for t in texts:
                    clean_t = t.lower().strip()
                    if any(h in clean_t for h in section_headers):
                        found = True
                        continue
                    if found:
                        if any(
                            h in clean_t
                            for h in [
                                "inbound",
                                "outbound",
                                "max",
                                "average",
                                "current",
                                "in",
                                "out",
                            ]
                        ) and not any(h in clean_t for h in section_headers):
                            pass
                        section_texts.append(t)

                def extract(keyword):
                    for i, text in enumerate(section_texts):
                        if keyword in text.lower():
                            for val_text in section_texts[i + 1 :]:
                                match = re.search(
                                    r"(\d+(?:[.,]\d+)?)\s*([MkGTmkgt]?(?:[Bb]?p?s?)?)", val_text
                                )
                                if match:
                                    value = match.group(1).replace(",", ".")
                                    unit = match.group(2).strip()
                                    if not unit:
                                        for unit_text in section_texts[i + 2 : i + 4]:
                                            unit_match = re.fullmatch(
                                                r"([MkGTmkgt])(?:[Bb]?p?s?)?", unit_text.strip()
                                            )
                                            if unit_match:
                                                unit = unit_match.group(1)
                                                break
                                    return f"{value} {unit}".strip()
                    for i, text in enumerate(section_texts):
                        match = re.search(
                            rf"{keyword}.*?(\d+(?:[.,]\d+)?)\s*([MkGTmkgt]?(?:[Bb]?p?s?)?)",
                            text,
                            re.IGNORECASE,
                        )
                        if match:
                            value = match.group(1).replace(",", ".")
                            unit = match.group(2).strip()
                            if not unit:
                                for unit_text in section_texts[i + 1 : i + 3]:
                                    unit_match = re.fullmatch(
                                        r"([MkGTmkgt])(?:[Bb]?p?s?)?", unit_text.strip()
                                    )
                                    if unit_match:
                                        unit = unit_match.group(1)
                                        break
                            return f"{value} {unit}".strip()
                    return "N/A"

                return {
                    "Current": extract("current"),
                    "Average": extract("average"),
                    "Maximum": extract("max"),
                }

            inbound = find_values_in_section(["inbound", "in"], all_texts)
            outbound = find_values_in_section(["outbound", "out"], all_texts)

            paddle_values = {
                "Inbound_Current": inbound["Current"],
                "Inbound_Average": inbound["Average"],
                "Inbound_Maximum": inbound["Maximum"],
                "Outbound_Current": outbound["Current"],
                "Outbound_Average": outbound["Average"],
                "Outbound_Maximum": outbound["Maximum"],
            }
            paddle_complete = all(v != "N/A" for v in paddle_values.values())
        except Exception as e:
            logger.error(f"Error during PaddleOCR processing: {e}")
            error_reason = "paddle_failed"

        return {
            "values": paddle_values,
            "confidence": paddle_confidence,
            "complete": paddle_complete,
            "error_reason": error_reason,
        }

    def _perform_single_extract(
        self, image_path: Path, config: Config = None, progress_callback=None, gemini_extractor=None
    ) -> dict[str, Any]:
        config = config or self.config
        result = {
            "values": {},
            "engine_used": "Paddle (Fallback)",
            "decision_reason": "both_incomplete",
            "paddle_confidence": 0.0,
            "paddle_values": {},
            "gemini_values": {},
            "gemini_model": "",
            "gemini_called": False,
            "attempted_models": [],
            "model_failures": {},
            "attempts": 0,
            "paddle_complete": False,
            "gemini_complete": False,
        }

        if progress_callback:
            progress_callback("start", image_path.name)

        paddle_fn = self._extract_paddle
        paddle_res = paddle_fn(image_path)
        if not isinstance(paddle_res, dict):
            paddle_res = {}

        paddle_values = paddle_res.get("values", {})
        paddle_confidence = float(paddle_res.get("confidence", 0.0))
        paddle_complete = bool(paddle_res.get("complete", False))

        # Decision Logic
        paddle_ok = paddle_complete and paddle_confidence >= config.ocr_confidence_threshold

        gemini_called = False
        gemini_res = {
            "values": {},
            "model": "",
            "complete": False,
            "error_reason": None,
            "attempted_models": [],
            "model_failures": {},
            "attempts": 0,
        }

        # Call Gemini if needed based on policy
        if config.ocr_gemini_observe or not paddle_ok:
            gemini_called = True
            extractor = gemini_extractor or self.gemini_extractor
            extracted_gemini = extractor.extract_legend(image_path)
            if isinstance(extracted_gemini, dict):
                gemini_res = {
                    "values": extracted_gemini.get("values", {}),
                    "model": extracted_gemini.get("model", ""),
                    "complete": bool(extracted_gemini.get("complete", False)),
                    "error_reason": extracted_gemini.get("error_reason"),
                    "attempted_models": extracted_gemini.get("attempted_models", []),
                    "model_failures": extracted_gemini.get("model_failures", {}),
                    "attempts": extracted_gemini.get("attempts", 0),
                }

        final_values = paddle_values
        engine_used, decision_reason = (
            "Paddle",
            "paddle_confident" if paddle_ok else "paddle_incomplete",
        )

        # Decide
        if paddle_ok and not config.ocr_gemini_observe:
            pass
        elif gemini_res["complete"]:
            engine_used = "Gemini"
            decision_reason = (
                "paddle_error"
                if not paddle_values
                else ("paddle_incomplete" if not paddle_complete else "low_confidence")
            )
            final_values = gemini_res["values"]
        elif paddle_complete:
            engine_used, decision_reason = "Paddle", "gemini_unavailable"
        else:
            decision_reason = "both_unknown"

        # Override if observing mismatch
        if config.ocr_gemini_observe and paddle_ok and gemini_res["complete"]:
            if paddle_values != gemini_res["values"]:
                engine_used, decision_reason, final_values = (
                    "Gemini",
                    "mismatch_observed",
                    gemini_res["values"],
                )

        result.update(
            {
                "values": final_values,
                "engine_used": engine_used,
                "decision_reason": decision_reason,
                "paddle_confidence": paddle_confidence,
                "paddle_values": paddle_values,
                "gemini_values": gemini_res["values"],
                "gemini_model": gemini_res["model"],
                "paddle_complete": paddle_complete,
                "gemini_complete": gemini_res["complete"],
                "gemini_called": gemini_called,
                "attempted_models": gemini_res.get("attempted_models", []),
                "model_failures": gemini_res.get("model_failures", {}),
                "attempts": gemini_res.get("attempts", 0),
                "gemini_error_reason": gemini_res.get("error_reason"),
            }
        )
        return result
