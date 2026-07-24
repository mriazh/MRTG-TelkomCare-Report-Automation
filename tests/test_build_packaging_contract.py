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
        self.assertEqual(name_count, 2, f"Expected exactly two name='MRTG-TelkomCare' declarations, found {name_count}")
        self.assertNotIn(".venv312/Lib/site-packages", content)
        self.assertIn("os.path.join(PROJECT_ROOT, '.venv312', 'Lib', 'site-packages', 'paddlex', 'configs')", content)

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

if __name__ == "__main__":
    unittest.main()
