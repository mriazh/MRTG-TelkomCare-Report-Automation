import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GUI_APP = REPO_ROOT / "src" / "mrtg_automation" / "gui" / "app.py"


class TestGuiStartupContract(unittest.TestCase):
    def test_gui_initializes_runtime_directories_before_setup(self):
        content = GUI_APP.read_text(encoding="utf-8")
        init_start = content.index("    def __init__(self):", content.index("class MainWindow"))
        init_end = content.index("    def check_resume_state", init_start)
        init_body = content[init_start:init_end]

        self.assertIn("ensure_directories(", init_body)
        self.assertLess(init_body.index("ensure_directories("), init_body.index("self.setup_ui()"))

    def test_open_output_folder_creates_reports_directory(self):
        content = GUI_APP.read_text(encoding="utf-8")
        method_start = content.index("    def open_output_folder(self):")
        method_end = content.index("    def pause_command", method_start)
        method_body = content[method_start:method_end]

        self.assertIn("self.reports_dir.mkdir(parents=True, exist_ok=True)", method_body)
        self.assertLess(method_body.index("self.reports_dir.mkdir"), method_body.index("os.startfile"))

    def test_configuration_rows_put_output_after_config(self):
        content = GUI_APP.read_text(encoding="utf-8")
        setup_start = content.index("    def setup_ui(self):")
        setup_end = content.index("    def _create_path_row", setup_start)
        setup_body = content[setup_start:setup_end]

        self.assertIn('form_layout.addRow("Config:", config_dir_row)', setup_body)
        self.assertIn('form_layout.addRow("Output:", output_root_row)', setup_body)
        self.assertLess(
            setup_body.index('form_layout.addRow("Config:", config_dir_row)'),
            setup_body.index('form_layout.addRow("Output:", output_root_row)'),
        )
