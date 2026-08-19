"""Release packaging contract regression tests.

Covers static contract verification for release packaging scripts:
- scripts/package_portable.ps1
- scripts/build_installer.ps1
- scripts/build_exe.ps1

Tests assert required contract patterns by inspecting script content without
executing PowerShell, tar, PyInstaller, or ISCC.
"""

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

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
# below re-read the real files and assert the snippets are present.
PACKAGE_PORTABLE_SCRIPT = REPO_ROOT / "scripts" / "package_portable.ps1"
BUILD_INSTALLER_SCRIPT = REPO_ROOT / "scripts" / "build_installer.ps1"
BUILD_EXE_SCRIPT = REPO_ROOT / "scripts" / "build_exe.ps1"


class TestReleasePackagingContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PACKAGE_PORTABLE_SCRIPT.exists():
            raise AssertionError(f"Missing script: {PACKAGE_PORTABLE_SCRIPT}")
        if not BUILD_INSTALLER_SCRIPT.exists():
            raise AssertionError(f"Missing script: {BUILD_INSTALLER_SCRIPT}")
        if not BUILD_EXE_SCRIPT.exists():
            raise AssertionError(f"Missing script: {BUILD_EXE_SCRIPT}")
        cls.portable_content = PACKAGE_PORTABLE_SCRIPT.read_text(encoding="utf-8")
        cls.installer_content = BUILD_INSTALLER_SCRIPT.read_text(encoding="utf-8")
        cls.build_exe_content = BUILD_EXE_SCRIPT.read_text(encoding="utf-8")

    def test_no_fallback_versions(self):
        """Ensure any quoted $AppVersion assignment in packaging scripts equals EXPECTED_VERSION."""
        pattern = re.compile(r'^\s*\$AppVersion\s*=\s*"([^"]+)"', re.MULTILINE)
        scripts = (
            (self.portable_content, "package_portable.ps1"),
            (self.installer_content, "build_installer.ps1"),
            (self.build_exe_content, "build_exe.ps1"),
        )
        for content, script_name in scripts:
            for match in pattern.finditer(content):
                assigned_version = match.group(1)
                self.assertEqual(
                    assigned_version,
                    EXPECTED_VERSION,
                    f"{script_name} contains obsolete fallback version assignment '{assigned_version}'",
                )

    def test_fail_fast_on_missing_app_info_or_unparsed_version(self):
        """Both packaging scripts must exit if app_info.py is missing or APP_VERSION unparsable."""
        for path, name in (
            (PACKAGE_PORTABLE_SCRIPT, "package_portable.ps1"),
            (BUILD_INSTALLER_SCRIPT, "build_installer.ps1"),
        ):
            content = path.read_text(encoding="utf-8")
            self.assertIn("app_info.py", content, f"{name} must reference app_info.py")
            self.assertIn("APP_VERSION", content, f"{name} must parse APP_VERSION")
            self.assertIn("exit 1", content, f"{name} must fail-fast on missing version")

    def test_repository_rooted_paths_usage(self):
        """All three scripts must use repository-rooted path variables."""
        for path, name in (
            (PACKAGE_PORTABLE_SCRIPT, "package_portable.ps1"),
            (BUILD_INSTALLER_SCRIPT, "build_installer.ps1"),
            (BUILD_EXE_SCRIPT, "build_exe.ps1"),
        ):
            content = path.read_text(encoding="utf-8")
            self.assertTrue(
                "$RootDir" in content or "$RepoRoot" in content,
                f"{name} must use repository-rooted path variable ($RootDir or $RepoRoot)",
            )

    def test_package_portable_uses_clean_staging(self):
        """package_portable.ps1 must populate a clean staging directory from manifest."""
        self.assertIn("$ManifestPath", self.portable_content)
        self.assertIn("$ManifestEntries", self.portable_content)
        self.assertIn("Get-Content $ManifestPath", self.portable_content)
        self.assertIn("$ManifestSet", self.portable_content)
        self.assertIn("Remove-Item -Recurse -Force", self.portable_content)
        self.assertIn("staging\\MRTG-TelkomCare-Portable", self.portable_content)

    def test_build_installer_uses_clean_staging(self):
        """build_installer.ps1 must populate a clean staging directory from manifest."""
        self.assertIn("$ManifestPath", self.installer_content)
        self.assertIn("$ManifestEntries", self.installer_content)
        self.assertIn("Get-Content $ManifestPath", self.installer_content)
        self.assertIn("$ManifestSet", self.installer_content)
        self.assertIn("Remove-Item -Recurse -Force", self.installer_content)
        self.assertIn("staging\\MRTG-TelkomCare-Installer", self.installer_content)
        self.assertIn("/DSourceDir=", self.installer_content)

    def test_explicit_allowlist_in_portable(self):
        """package_portable.ps1 must copy from manifest entries only (no whole-directory copies)."""
        self.assertIn("Get-Content $ManifestPath", self.portable_content)
        self.assertIn("foreach ($relPath in $ManifestEntries)", self.portable_content)
        self.assertIn("Copy-Item", self.portable_content)
        # Must not use whole-directory patterns like "Src = \"_internal\""
        for directory in ("_internal", "config", "assets"):
            self.assertNotIn(
                f'Src = "{directory}"',
                self.portable_content,
                f"package_portable.ps1 must not use whole-directory allowlist for {directory}",
            )
        self.assertNotIn("_internal\\paddle\\**", self.portable_content)
        self.assertNotIn("_internal\\paddlex\\**", self.portable_content)

    def test_explicit_allowlist_in_installer(self):
        """build_installer.ps1 must copy from manifest entries only (no whole-directory copies)."""
        self.assertIn("Get-Content $ManifestPath", self.installer_content)
        self.assertIn("foreach ($relPath in $ManifestEntries)", self.installer_content)
        self.assertIn("Copy-Item", self.installer_content)
        for directory in ("_internal", "config", "assets"):
            self.assertNotIn(
                f'Src = "{directory}"',
                self.installer_content,
                f"build_installer.ps1 must not use whole-directory allowlist for {directory}",
            )
        self.assertNotIn("_internal\\paddle\\**", self.installer_content)
        self.assertNotIn("_internal\\paddlex\\**", self.installer_content)

    def test_private_target_csv_absent_from_portable_allowlist(self):
        """Private CSV must not be copied by package_portable.ps1 (manifest excludes it)."""
        # The private CSV should appear in forbidden-check lists but never as a copied file
        # Check it doesn't appear in copy operations or allowlists
        self.assertNotIn(
            'Src = "config\\list_mrtg_targets.csv"',
            self.portable_content,
            "package_portable.ps1 must not copy private CSV via Src allowlist",
        )
        self.assertNotRegex(
            self.portable_content,
            r"(?im)^\s*Copy-Item\b[^\r\n]*list_mrtg_targets\.csv",
            "package_portable.ps1 must not copy private CSV",
        )
        # But it SHOULD appear in forbidden-check lists (this is correct behavior)
        self.assertIn(
            "config\\list_mrtg_targets.csv",
            self.portable_content,
            "package_portable.ps1 must check for forbidden private CSV",
        )

    def test_private_target_csv_absent_from_installer_allowlist(self):
        """Private CSV must not be copied by build_installer.ps1 (manifest excludes it)."""
        # The private CSV should appear in forbidden-check lists but never as a copied file
        self.assertNotIn(
            'Src = "config\\list_mrtg_targets.csv"',
            self.installer_content,
            "build_installer.ps1 must not copy private CSV via Src allowlist",
        )
        self.assertNotRegex(
            self.installer_content,
            r"(?im)^\s*Copy-Item\b[^\r\n]*list_mrtg_targets\.csv",
            "build_installer.ps1 must not copy private CSV",
        )
        # But it SHOULD appear in forbidden-check lists (this is correct behavior)
        self.assertIn(
            "config\\list_mrtg_targets.csv",
            self.installer_content,
            "build_installer.ps1 must check for forbidden private CSV",
        )

    def test_private_target_csv_absent_from_build_exe_safe_configs(self):
        """build_exe.ps1 must not copy the private CSV; only the sanitized example."""
        self.assertIn(
            "list_mrtg_targets.example.csv",
            self.build_exe_content,
            "build_exe.ps1 must copy the sanitized example CSV",
        )
        # The private CSV should appear in forbidden-check lists in build_exe
        self.assertIn(
            "config\\list_mrtg_targets.csv",
            self.build_exe_content,
            "build_exe.ps1 must check for forbidden private CSV in manifest",
        )
        self.assertNotRegex(
            self.build_exe_content,
            r"(?im)^\s*Copy-Item\b[^\r\n]*list_mrtg_targets\.csv",
            "build_exe.ps1 must not copy private CSV",
        )

    def test_forbidden_env_entry_rejected_in_portable(self):
        """package_portable.ps1 must reject .env in forbidden checks."""
        self.assertIn("config\\.env", self.portable_content)
        self.assertIn("ForbiddenFiles", self.portable_content)

    def test_forbidden_target_csv_entry_rejected_in_portable(self):
        """package_portable.ps1 must reject private target CSV in forbidden checks."""
        self.assertIn("config\\list_mrtg_targets.csv", self.portable_content)
        self.assertIn("ForbiddenFiles", self.portable_content)

    def test_forbidden_data_dir_rejected_in_portable(self):
        """package_portable.ps1 must reject data/ directory in forbidden checks."""
        self.assertIn("data", self.portable_content)
        self.assertIn("ForbiddenDirs", self.portable_content)

    def test_forbidden_output_dir_rejected_in_portable(self):
        """package_portable.ps1 must reject output/ directory in forbidden checks."""
        self.assertIn("output", self.portable_content)
        self.assertIn("ForbiddenDirs", self.portable_content)

    def test_forbidden_target_csv_rejected_in_installer(self):
        """build_installer.ps1 must reject private target CSV in forbidden checks."""
        self.assertIn("config\\list_mrtg_targets.csv", self.installer_content)
        self.assertIn("ForbiddenFiles", self.installer_content)

    def test_forbidden_env_rejected_in_installer(self):
        """build_installer.ps1 must reject .env in forbidden checks."""
        self.assertIn("config\\.env", self.installer_content)
        self.assertIn("ForbiddenFiles", self.installer_content)

    def test_forbidden_data_dir_rejected_in_installer(self):
        """build_installer.ps1 must reject data/ directory in forbidden checks."""
        self.assertIn("data", self.installer_content)
        self.assertIn("ForbiddenDirs", self.installer_content)

    def test_forbidden_output_dir_rejected_in_installer(self):
        """build_installer.ps1 must reject output/ directory in forbidden checks."""
        self.assertIn("output", self.installer_content)
        self.assertIn("ForbiddenDirs", self.installer_content)

    def test_sanitized_example_csv_in_portable_allowlist(self):
        """package_portable.ps1 must include sanitized example CSV via manifest/required files."""
        # The sanitized example should be present through manifest/required validation
        self.assertIn("list_mrtg_targets.example.csv", self.portable_content)

    def test_sanitized_example_csv_in_installer_allowlist(self):
        """build_installer.ps1 must include sanitized example CSV via manifest/required files."""
        self.assertIn("list_mrtg_targets.example.csv", self.installer_content)

    def test_sanitized_example_csv_in_build_exe_safe_configs(self):
        """build_exe.ps1 must copy the sanitized example CSV as a safe config."""
        self.assertIn("list_mrtg_targets.example.csv", self.build_exe_content)

    def test_inno_setup_uses_source_dir_define(self):
        """Inno Setup script must use SourceDir define from build_installer.ps1."""
        iss_path = REPO_ROOT / "installer" / "MRTG-TelkomCare.iss"
        self.assertTrue(iss_path.exists(), f"Missing Inno Setup script: {iss_path}")
        iss_content = iss_path.read_text(encoding="utf-8")
        # Inno Setup must reference SourceDir for file sourcing
        self.assertIn("SourceDir", iss_content)
        # Must reference the executable by name
        self.assertIn("MRTG-TelkomCare.exe", iss_content)

    def test_accepts_safe_manifest(self):
        """Manifest validation must accept the approved exact file list."""
        allowed = (
            "MRTG-TelkomCare.exe",
            "config/.env.example",
            "config/list_mrtg_targets.example.csv",
            "config/list_mrtg_data_position.example.txt",
            "config/list_mrtg_data_position_img_only.example.txt",
            "config/MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx",
            "config/MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx",
            "assets/app_icon.ico",
            "_internal/base_library.zip",
            "_internal/python312.dll",
            "_internal/python3.dll",
            "_internal/paddlex/configs/pipelines/OCR.yaml",
            "_internal/paddle/libs/mklml.dll",
        )
        self.assertEqual(validate_release_manifest(allowed), [])

    def test_rejects_config_dot_env(self):
        self.assertEqual(validate_release_manifest(["config/.env"]), ["config/.env"])

    def test_rejects_private_target_csv(self):
        self.assertEqual(
            validate_release_manifest(["config/list_mrtg_targets.csv"]),
            ["config/list_mrtg_targets.csv"],
        )

    def test_rejects_private_data_position_txt(self):
        self.assertEqual(
            validate_release_manifest(["config/list_mrtg_data_position.txt"]),
            ["config/list_mrtg_data_position.txt"],
        )
        self.assertEqual(
            validate_release_manifest(["config/list_mrtg_data_position_img_only.txt"]),
            ["config/list_mrtg_data_position_img_only.txt"],
        )

    def test_rejects_data_dir_entries(self):
        self.assertEqual(
            validate_release_manifest(["data/MRTG-Data/scraped.json"]),
            ["data/MRTG-Data/scraped.json"],
        )

    def test_rejects_output_subdirectories(self):
        for entry in (
            "output/logs/app.log",
            "output/reports/report.xlsx",
            "output/state/session.json",
            "output/screenshots/capture.png",
        ):
            with self.subTest(entry=entry):
                self.assertEqual(validate_release_manifest([entry]), [entry])

    def test_rejects_arbitrary_stale_files(self):
        for entry in (
            "_internal/paddle/stale.bin",
            "_internal/paddlex/stale.txt",
            "_internal/stale.dll",
            "_internal/stale.pyd",
            "config/stale.txt",
            "assets/unexpected.png",
            "stale.txt",
        ):
            with self.subTest(entry=entry):
                self.assertEqual(validate_release_manifest([entry]), [entry])

    def test_rejects_legacy_private_config_files(self):
        for entry in (
            "config/SID-MRTG.txt",
            "config/GRAPH-TITLE-MRTG.txt",
            "config/report-items.txt",
        ):
            with self.subTest(entry=entry):
                self.assertEqual(validate_release_manifest([entry]), [entry])

    def test_normalizes_backslashes(self):
        """Manifest validation must normalize Windows backslashes to forward slashes."""
        self.assertEqual(validate_release_manifest(["config\\.env"]), ["config/.env"])
        self.assertEqual(
            validate_release_manifest(["_internal\\paddle\\stale.bin"]),
            ["_internal/paddle/stale.bin"],
        )


def validate_release_manifest(
    entries,
    allowed_files=(
        "MRTG-TelkomCare.exe",
        "config/.env.example",
        "config/list_mrtg_targets.example.csv",
        "config/list_mrtg_data_position.example.txt",
        "config/list_mrtg_data_position_img_only.example.txt",
        "config/MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx",
        "config/MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx",
        "assets/app_icon.ico",
        "_internal/base_library.zip",
        "_internal/python312.dll",
        "_internal/python3.dll",
        "_internal/paddlex/configs/pipelines/OCR.yaml",
        "_internal/paddle/libs/mklml.dll",
    ),
):
    """Return forbidden or unapproved archive-relative paths."""
    FORBIDDEN_ENTRIES = (
        "config/.env",
        "config/SID-MRTG.txt",
        "config/GRAPH-TITLE-MRTG.txt",
        "config/report-items.txt",
        "config/list_mrtg_targets.csv",
        "config/list_mrtg_data_position.txt",
        "config/list_mrtg_data_position_img_only.txt",
    )
    FORBIDDEN_DIR_PREFIXES = ("data/", "output/")
    violations = []
    for entry in entries:
        normalized = entry.replace("\\", "/").lstrip("/")
        if not normalized:
            continue
        if (
            normalized in FORBIDDEN_ENTRIES
            or normalized.startswith(FORBIDDEN_DIR_PREFIXES)
            or normalized not in allowed_files
        ):
            violations.append(normalized)
    return violations


if __name__ == "__main__":
    unittest.main()
