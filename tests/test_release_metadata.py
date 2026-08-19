"""Release metadata and packaging contract regression tests.

Covers FR-006 (automated regression coverage for version consistency,
executable and release artifact naming, README command accuracy, and
packaging metadata behavior) and SC-004 (the release-contract regression
tests pass without invoking PyInstaller or Inno Setup).

These tests read the actual repository metadata and packaging files --
pyproject.toml, README.md, installer/MRTG-TelkomCare.iss,
mrtg_telkomcare.spec, scripts/package_portable.ps1, and
scripts/build_installer.ps1 -- plus the Python package metadata. They never
import the PyInstaller spec and never execute PowerShell, PyInstaller, or
Inno Setup.
"""

import re
import sys
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"

# The package lives under src/ (src-layout), so make it importable even
# when the project has not been pip-installed.
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import mrtg_automation
from mrtg_automation import app_info

# --- Expected values (release 1.0.2) --------------------------------------
EXPECTED_VERSION = "1.0.3"
EXPECTED_EXE_NAME = "MRTG-TelkomCare.exe"
EXPECTED_EXE_STEM = "MRTG-TelkomCare"
EXPECTED_SETUP_ASSET_PREFIX = "MRTG-TelkomCare-Setup"
EXPECTED_SETUP_ASSET_SUFFIX = ".exe"
EXPECTED_SETUP_INSTALLER_NAME = "MRTG-TelkomCare-Setup-v1.0.3.exe"
EXPECTED_PORTABLE_ARCHIVE_NAME = "MRTG-TelkomCare-v1.0.3-portable.zip"
STALE_EXE_NAME = "MRTG-TelkomCare-Automation.exe"

# --- Frozen packaging-text snippets (verified at release 1.0.2) -----------
# These are the exact strings the packaging files must contain; the tests
# below re-read the real files and assert the snippets appear in them.
ISS_VERSION_DEFINE = f'#define MyAppVersion "{EXPECTED_VERSION}"'
ISS_EXE_NAME_DEFINE = f'#define MyAppExeName "{EXPECTED_EXE_NAME}"'
ISS_OUTPUT_BASE_FILENAME = f"OutputBaseFilename={EXPECTED_SETUP_ASSET_PREFIX}-v{{#MyAppVersion}}"
PS1_PORTABLE_EXE_PATH = f'$ExePath = Join-Path $DistDir "{EXPECTED_EXE_NAME}"'
PS1_PORTABLE_ZIP_NAME = f'$ZipName = "{EXPECTED_EXE_STEM}-v$AppVersion-portable.zip"'
PS1_INSTALLER_EXE_PATH = r'$ExePath = Join-Path $RootDir "dist\MRTG-TelkomCare\MRTG-TelkomCare.exe"'
PS1_ISCC_INVOCATION = (
    '& $ISCC "/DMyAppVersion=$AppVersion" "/DSourceDir=$StagingRelativePath" $IssPath'
)
PS1_RELEASE_REPORT = r"release\MRTG-TelkomCare-Setup-v$AppVersion.exe"

# --- Naming regexes -------------------------------------------------------
EXE_NAME_RE = re.compile(r"\bMRTG-TelkomCare\.exe\b")
SETUP_ARTIFACT_RE = re.compile(r"MRTG-TelkomCare-Setup-v1\.0\.3\.exe")
PORTABLE_ARTIFACT_RE = re.compile(r"MRTG-TelkomCare-v1\.0\.3-portable\.zip")
STALE_EXE_NAME_RE = re.compile(r"MRTG-TelkomCare-Automation\.exe")


def _read_text(relative_path: str) -> str:
    """Read a repository file as UTF-8 text for contract assertions."""
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


class TestPackageMetadata(unittest.TestCase):
    """Test case 1: package and app metadata constants (FR-006)."""

    def test_package_version_equals_expected(self):
        self.assertEqual(mrtg_automation.__version__, EXPECTED_VERSION)

    def test_app_version_equals_expected(self):
        self.assertEqual(app_info.APP_VERSION, EXPECTED_VERSION)

    def test_installer_asset_prefix_equals_expected(self):
        self.assertEqual(app_info.INSTALLER_ASSET_PREFIX, EXPECTED_SETUP_ASSET_PREFIX)

    def test_installer_asset_suffix_equals_expected(self):
        self.assertEqual(app_info.INSTALLER_ASSET_SUFFIX, EXPECTED_SETUP_ASSET_SUFFIX)


class TestPyprojectVersion(unittest.TestCase):
    """Test case 2: pyproject.toml project version agrees with the package."""

    def _pyproject_version(self) -> str:
        with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
            return tomllib.load(handle)["project"]["version"]

    def test_pyproject_version_equals_expected(self):
        self.assertEqual(self._pyproject_version(), EXPECTED_VERSION)

    def test_pyproject_version_matches_package_version(self):
        self.assertEqual(self._pyproject_version(), mrtg_automation.__version__)


class TestDerivedArtifactNames(unittest.TestCase):
    """Test case 3: derived installer and portable names equal v1.0.2 names."""

    def test_installer_name_derived_from_app_info(self):
        derived = (
            f"{app_info.INSTALLER_ASSET_PREFIX}-v{app_info.APP_VERSION}"
            f"{app_info.INSTALLER_ASSET_SUFFIX}"
        )
        self.assertEqual(derived, EXPECTED_SETUP_INSTALLER_NAME)

    def test_portable_archive_name_derived_from_exe_stem(self):
        portable_prefix = Path(EXPECTED_EXE_NAME).stem
        derived = f"{portable_prefix}-v{EXPECTED_VERSION}-portable.zip"
        self.assertEqual(derived, EXPECTED_PORTABLE_ARCHIVE_NAME)

    def test_executable_name_matches_exe_stem(self):
        self.assertEqual(f"{Path(EXPECTED_EXE_NAME).stem}.exe", EXPECTED_EXE_NAME)


class TestReadmeContract(unittest.TestCase):
    """Test case 5 / FR-006: README commands reference exact artifact names."""

    def setUp(self):
        self.readme = _read_text("README.md")

    def test_readme_contains_installer_artifact_name(self):
        self.assertIn(EXPECTED_SETUP_INSTALLER_NAME, self.readme)

    def test_readme_contains_portable_archive_name(self):
        self.assertIn(EXPECTED_PORTABLE_ARCHIVE_NAME, self.readme)

    def test_readme_contains_packaged_executable_name(self):
        self.assertIn(EXPECTED_EXE_NAME, self.readme)

    def test_readme_does_not_contain_stale_executable_name(self):
        self.assertNotIn(STALE_EXE_NAME, self.readme)


class TestInstallerScriptContract(unittest.TestCase):
    """FR-006: Inno Setup script embeds version, exe name, and output name."""

    def setUp(self):
        self.iss = _read_text("installer/MRTG-TelkomCare.iss")

    def test_iss_contains_version_define(self):
        self.assertIn(ISS_VERSION_DEFINE, self.iss)

    def test_iss_contains_exe_name_define(self):
        self.assertIn(ISS_EXE_NAME_DEFINE, self.iss)

    def test_iss_contains_output_base_filename_template(self):
        self.assertIn(ISS_OUTPUT_BASE_FILENAME, self.iss)


class TestPyInstallerSpecContract(unittest.TestCase):
    """FR-006: spec names the packaged executable for EXE and COLLECT."""

    def test_spec_declares_exe_name_twice(self):
        spec = _read_text("mrtg_telkomcare.spec")
        self.assertEqual(spec.count("name='MRTG-TelkomCare'"), 2)
        self.assertIn("MRTG-TelkomCare", spec)

    def test_spec_uses_specpath_for_project_root(self):
        spec = _read_text("mrtg_telkomcare.spec")
        self.assertIn("SPECPATH", spec)
        self.assertNotIn("__file__", spec)


class TestPortablePackagingScriptContract(unittest.TestCase):
    """FR-006: package_portable.ps1 names exe and portable zip archive."""

    def setUp(self):
        self.ps1 = _read_text("scripts/package_portable.ps1")

    def test_ps1_contains_exe_path_assignment(self):
        self.assertIn(PS1_PORTABLE_EXE_PATH, self.ps1)

    def test_ps1_contains_zip_name_assignment(self):
        self.assertIn(PS1_PORTABLE_ZIP_NAME, self.ps1)


class TestInstallerBuildScriptContract(unittest.TestCase):
    """FR-006: build_installer.ps1 drives Inno with the app version."""

    def setUp(self):
        self.ps1 = _read_text("scripts/build_installer.ps1")

    def test_ps1_contains_exe_path_assignment(self):
        self.assertIn(PS1_INSTALLER_EXE_PATH, self.ps1)

    def test_ps1_contains_iscc_invocation(self):
        self.assertIn(PS1_ISCC_INVOCATION, self.ps1)

    def test_ps1_contains_release_report_path(self):
        self.assertIn(PS1_RELEASE_REPORT, self.ps1)


class TestNamingRegexContract(unittest.TestCase):
    """Regex-level artifact naming checks (FR-006 executable/artifact naming)."""

    def test_exe_name_regex_matches_expected_executable(self):
        self.assertIsNotNone(EXE_NAME_RE.search(EXPECTED_EXE_NAME))

    def test_setup_artifact_regex_matches_expected_installer(self):
        self.assertIsNotNone(SETUP_ARTIFACT_RE.search(EXPECTED_SETUP_INSTALLER_NAME))

    def test_portable_artifact_regex_matches_expected_archive(self):
        self.assertIsNotNone(PORTABLE_ARTIFACT_RE.search(EXPECTED_PORTABLE_ARCHIVE_NAME))

    def test_stale_exe_name_regex_matches_stale_name(self):
        self.assertIsNotNone(STALE_EXE_NAME_RE.search(STALE_EXE_NAME))

    def test_stale_exe_name_regex_rejects_expected_names(self):
        self.assertIsNone(STALE_EXE_NAME_RE.search(EXPECTED_EXE_NAME))
        self.assertIsNone(STALE_EXE_NAME_RE.search(EXPECTED_SETUP_INSTALLER_NAME))
        self.assertIsNone(STALE_EXE_NAME_RE.search(EXPECTED_PORTABLE_ARCHIVE_NAME))


if __name__ == "__main__":
    unittest.main()
