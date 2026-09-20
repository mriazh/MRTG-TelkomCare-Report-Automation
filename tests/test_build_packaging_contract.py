import os
import unittest


class TestPackagingContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.BUILD_SCRIPT = os.path.join(cls.REPO_ROOT, "scripts", "build_exe.ps1")
        cls.SPEC_FILE = os.path.join(cls.REPO_ROOT, "mrtg_telkomcare.spec")
        cls.DIST_DIR = os.path.join(cls.REPO_ROOT, "dist")
        cls.EXPECTED_EXE_DIR = os.path.join(cls.DIST_DIR, "MRTG-TelkomCare")
        cls.EXPECTED_EXE = os.path.join(cls.EXPECTED_EXE_DIR, "MRTG-TelkomCare.exe")

    def test_script_and_spec_exist(self):
        self.assertTrue(os.path.exists(self.BUILD_SCRIPT))
        self.assertTrue(os.path.exists(self.SPEC_FILE))

    def test_spec_contract(self):
        with open(self.SPEC_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("PROJECT_ROOT =", content)
        self.assertIn("gui_launcher.py", content)
        name_count = content.count("name='MRTG-TelkomCare'")
        self.assertEqual(
            name_count,
            2,
            f"Expected exactly two name='MRTG-TelkomCare' declarations, found {name_count}",
        )
        self.assertNotIn(".venv312/Lib/site-packages", content)
        self.assertIn(
            "os.path.join(PROJECT_ROOT, '.venv312', 'Lib', 'site-packages', 'paddlex', 'configs')",
            content,
        )

    def test_build_script_contract(self):
        # This is a basic check. Actual execution is separate.
        with open(self.BUILD_SCRIPT, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("$RepoRoot", content)
        self.assertIn("$VenvDir", content)
        self.assertIn("$SpecFile", content)
        self.assertIn("$DistDir", content)
        self.assertIn("$ExpectedExe", content)
        # Check for forbidden patterns directly
        self.assertNotIn(".venv312/Lib/site-packages", content)
        self.assertNotIn(".git", content)


class TestDependencyLockContract(unittest.TestCase):
    """REQ-36: deterministic `requirements.lock` exported from `uv.lock`."""

    @classmethod
    def setUpClass(cls):
        cls.REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.LOCKFILE = os.path.join(cls.REPO_ROOT, "requirements.lock")

    def test_lockfile_exists(self):
        self.assertTrue(os.path.exists(self.LOCKFILE), "requirements.lock is missing")

    def test_lockfile_is_fully_pinned(self):
        with open(self.LOCKFILE, "r", encoding="utf-8") as f:
            lines = [line.rstrip("\n") for line in f if line.strip()]

        requirements = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("--hash") or stripped == "\\":
                continue
            if "==" not in stripped:
                self.fail(f"unpinned requirement in requirements.lock: {stripped}")
            requirements.append(stripped)

        self.assertGreater(len(requirements), 0, "no pinned requirements found")
        self.assertNotIn("-e .", lines, "editable project reference is not portable")

    def test_lockfile_covers_core_and_extras(self):
        with open(self.LOCKFILE, "r", encoding="utf-8") as f:
            content = f.read().lower()
        for package in ("selenium==", "pydantic==", "pyotp==", "pyside6==", "paddleocr=="):
            self.assertIn(package, content, f"{package} missing from requirements.lock")


class TestCiWorkflowContract(unittest.TestCase):
    """REQ-37: automated GitHub Actions CI workflow."""

    @classmethod
    def setUpClass(cls):
        cls.REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.WORKFLOW = os.path.join(cls.REPO_ROOT, ".github", "workflows", "ci.yml")

    def test_workflow_exists(self):
        self.assertTrue(os.path.exists(self.WORKFLOW), ".github/workflows/ci.yml is missing")

    def test_workflow_contract(self):
        with open(self.WORKFLOW, "r", encoding="utf-8") as f:
            content = f.read()

        for branch in ("main", "master"):
            self.assertIn(branch, content)
        self.assertIn("actions/checkout@v4", content)
        self.assertIn("astral-sh/setup-uv@v5", content)
        self.assertIn("enable-cache", content)
        self.assertIn("3.12", content)
        self.assertIn("uv sync --locked --extra ocr --extra gui", content)
        self.assertIn("ruff check src tests", content)
        self.assertIn("ruff format --check src tests", content)
        self.assertIn("mypy src tests", content)
        self.assertIn("pytest", content)


if __name__ == "__main__":
    unittest.main()
