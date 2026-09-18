import contextlib
import io
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

from dotenv import dotenv_values
from PySide6.QtCore import QDate, QObject, QSettings, QThread, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from mrtg_automation import app_info
from mrtg_automation.cli import run_full_command, run_report_command, run_scrape_command
from mrtg_automation.gui.about_dialog import show_about_dialog
from mrtg_automation.gui.update_checker import UpdateManager
from mrtg_automation.shared.browser_detection import (
    get_browser_display_name,
)
from mrtg_automation.shared.paths import (
    DEFAULT_CONFIG_DIR,
    DEFAULT_OUTPUT_DIR,
    ROOT_DIR,
    ensure_directories,
    get_output_paths,
)
from mrtg_automation.shared.resume_state import (
    clear_resume_state,
    format_resume_summary,
    has_unfinished_resume_state,
    load_resume_state,
    save_resume_state,
)


class Worker(QObject):
    log_signal = Signal(str)
    finished_signal = Signal(int)

    def __init__(
        self,
        mode,
        date_mode,
        date_str,
        start_date_str,
        end_date_str,
        targets,
        report_mode,
        headless,
        browser_type="auto",
        resume_state=None,
        resume_mode=False,
        output_dir=None,
        data_dir=None,
        config_dir=None,
        reports_dir=None,
    ):
        super().__init__()
        self.mode = mode
        self.date_mode = date_mode
        self.date_str = date_str
        self.start_date_str = start_date_str
        self.end_date_str = end_date_str
        self.targets = targets
        self.report_mode = report_mode
        self.headless = headless
        self.browser_type = browser_type
        self.resume_state = resume_state
        self.resume_mode = resume_mode
        self.output_dir = output_dir
        self.data_dir = data_dir
        self.config_dir = config_dir
        self.reports_dir = reports_dir
        self.cancel_event = threading.Event()
        self.pause_event = threading.Event()

    def request_stop(self):
        self.cancel_event.set()
        self.pause_event.clear()
        try:
            self.log_signal.emit(
                "Stop requested. Cancelling startup/login or waiting for current item to finish..."
            )
        except RuntimeError:
            pass  # Ignore if Qt window/signal source is destroyed during app close

    def run(self):
        def _is_stacktrace_noise(line: str) -> bool:
            """Check if a single line is Selenium/OS stacktrace noise to be skipped."""
            stripped = line.strip()
            if not stripped:
                return True
            noise_markers = [
                "Stacktrace:",
                "Chromedriver!",
                "(Session info:",
                "For documentation on this error",
                "Build info:",
                "System info:",
                "Driver info:",
                "KERNEL32!",
                "Ntdll!",
            ]
            for marker in noise_markers:
                if marker in stripped:
                    return True
            if stripped.startswith("0x") or stripped.startswith("0X"):
                return True
            if stripped.startswith("#") and any(c in stripped for c in ["0x", "0X"]):
                return True
            if stripped.endswith("+"):
                return True
            return False

        class StreamRedirector(io.StringIO):
            """Redirects stdout/stderr to the GUI log panel.
            Simple real-time line filter: buffers only to assemble complete lines,
            processes each line immediately, and skips stacktrace noise lines.
            """

            def __init__(self, signal):
                super().__init__()
                self.signal = signal
                self._buffer = ""

            def write(self, text):
                if text:
                    self._buffer += text
                    while "\n" in self._buffer:
                        line, self._buffer = self._buffer.split("\n", 1)
                        if not _is_stacktrace_noise(line):
                            self.signal.emit(line.strip())
                super().write(text)

            def flush(self):
                if self._buffer.strip() and not _is_stacktrace_noise(self._buffer):
                    try:
                        self.signal.emit(self._buffer.strip())
                    except RuntimeError:
                        pass  # Qt object already deleted; ignore during shutdown
                self._buffer = ""
                super().flush()

        redirector = StreamRedirector(self.log_signal)

        exit_code = 1
        with contextlib.redirect_stdout(redirector), contextlib.redirect_stderr(redirector):
            try:
                self.log_signal.emit("=" * 70)
                self.log_signal.emit(f"RUN START: {self.mode}")
                self.log_signal.emit("=" * 70)

                d_str = self.date_str if self.date_mode == "Single Date" else None
                s_str = self.start_date_str if self.date_mode == "Date Range" else None
                e_str = self.end_date_str if self.date_mode == "Date Range" else None

                if self.mode in ("Scrape", "Full Pipeline"):
                    os.environ["BROWSER_TYPE"] = self.browser_type
                    from mrtg_automation.config import Config

                    cfg = Config(config_dir=self.config_dir)
                    effective = getattr(
                        cfg, "effective_browser_type", getattr(cfg, "browser_type", "chrome")
                    )
                    self.log_signal.emit(
                        f"Browser configuration: {cfg.browser_type} (effective: {effective})"
                    )

                if self.date_mode == "Single Date":
                    self.log_signal.emit(f"Date: {self.date_str}")
                else:
                    self.log_signal.emit(
                        f"Date range: {self.start_date_str} to {self.end_date_str}"
                    )

                if self.mode == "Scrape":
                    exit_code = run_scrape_command(
                        date_str=d_str,
                        targets_filter=self.targets,
                        headless=self.headless,
                        start_date_str=s_str,
                        end_date_str=e_str,
                        cancel_event=self.cancel_event,
                        pause_event=self.pause_event,
                        resume_state=self.resume_state,
                        resume_mode=self.resume_mode,
                        output_dir=self.output_dir,
                        data_dir=self.data_dir,
                        config_dir=self.config_dir,
                    )
                elif self.mode == "Report":
                    exit_code = run_report_command(
                        mode=self.report_mode,
                        date_str=d_str,
                        no_images=False,
                        start_date_str=s_str,
                        end_date_str=e_str,
                        cancel_event=self.cancel_event,
                        pause_event=self.pause_event,
                        resume_state=self.resume_state,
                        resume_mode=self.resume_mode,
                        output_dir=self.output_dir,
                        data_dir=self.data_dir,
                        config_dir=self.config_dir,
                        reports_dir=self.reports_dir,
                    )
                elif self.mode == "Full Pipeline":
                    exit_code = run_full_command(
                        date_str=d_str,
                        targets_filter=self.targets,
                        report_mode=self.report_mode,
                        headless=self.headless,
                        no_images=False,
                        start_date_str=s_str,
                        end_date_str=e_str,
                        cancel_event=self.cancel_event,
                        pause_event=self.pause_event,
                        resume_state=self.resume_state,
                        resume_mode=self.resume_mode,
                        output_dir=self.output_dir,
                        data_dir=self.data_dir,
                        config_dir=self.config_dir,
                        reports_dir=self.reports_dir,
                    )
            except Exception as e:
                self.log_signal.emit(f"[FATAL] {str(e)}")
                exit_code = 1

        self.log_signal.emit("=" * 70)
        self.log_signal.emit(f"RUN END: {self.mode} (exit_code={exit_code})")
        self.log_signal.emit("=" * 70)

        self.finished_signal.emit(exit_code)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MRTG TelkomCare Report Automation")
        self.resize(800, 600)

        self.settings = QSettings("MRTG", "TelkomCareReportAutomation")
        raw_output_root = self.settings.value("output_root", None) or self.settings.value(
            "output_dir", None
        )
        self.output_root = Path(raw_output_root) if raw_output_root else DEFAULT_OUTPUT_DIR
        self.config_dir = Path(self.settings.value("config_dir", str(DEFAULT_CONFIG_DIR)))
        self.paths = get_output_paths(output_root=self.output_root)
        self.data_dir = self.paths.data_dir
        self.reports_dir = self.paths.reports_dir
        self.logs_dir = self.paths.logs_dir

        ensure_directories(output_root=self.output_root)

        self.worker_thread = None
        self.worker = None
        self.pending_resume_state = None
        self.has_incomplete_data = False
        self._warned_incomplete_item = False

        self.update_manager = UpdateManager(self)

        self.setup_ui()
        icon_path_ico = ROOT_DIR / "assets" / "app_icon.ico"
        icon_path_png = ROOT_DIR / "assets" / "app_icon.png"
        icon_path_svg = ROOT_DIR / "assets" / "app_icon.svg"
        if icon_path_ico.exists():
            self.setWindowIcon(QIcon(str(icon_path_ico)))
        elif icon_path_png.exists():
            self.setWindowIcon(QIcon(str(icon_path_png)))
        elif icon_path_svg.exists():
            self.setWindowIcon(QIcon(str(icon_path_svg)))

        self.check_resume_state()

    def check_resume_state(self):
        if has_unfinished_resume_state():
            state = load_resume_state()
            if not state:
                return

            msg = QMessageBox(self)
            msg.setWindowTitle("Unfinished Run Found")
            msg.setText(
                "An unfinished run was found. What would you like to do?\n\n"
                + format_resume_summary(state)
            )
            btn_resume = msg.addButton("Resume", QMessageBox.AcceptRole)
            btn_new = msg.addButton("Start New", QMessageBox.RejectRole)
            btn_discard = msg.addButton("Discard", QMessageBox.DestructiveRole)
            msg.exec()

            if msg.clickedButton() == btn_resume:
                self.log_message("Resume state loaded. Click Resume to continue.")
                self.pending_resume_state = state
                self.mode_cb.setCurrentText(state.get("operation_mode", "Scrape"))
                try:
                    if state.get("date_str"):
                        parsed = QDate.fromString(state.get("date_str"), "yyyyMMdd")
                        if parsed.isValid():
                            self.start_date_input.setDate(parsed)
                            self.end_date_input.setDate(parsed)
                    else:
                        if state.get("start_date_str"):
                            parsed = QDate.fromString(state.get("start_date_str"), "yyyyMMdd")
                            if parsed.isValid():
                                self.start_date_input.setDate(parsed)
                        if state.get("end_date_str"):
                            parsed = QDate.fromString(state.get("end_date_str"), "yyyyMMdd")
                            if parsed.isValid():
                                self.end_date_input.setDate(parsed)
                except Exception:
                    pass
                self.targets_cb.setCurrentText(state.get("targets_filter", "image"))
                self.report_mode_cb.setCurrentText(state.get("report_mode", "image"))
                if state.get("output_dir"):
                    self._set_path("output_root", state["output_dir"], self.output_root_input)
                elif state.get("output_root"):
                    self._set_path("output_root", state["output_root"], self.output_root_input)
                if state.get("config_dir"):
                    self._set_path("config_dir", state["config_dir"], self.config_dir_input)
                if state.get("browser_type"):
                    b_type = state.get("browser_type").lower()
                    idx = self.browser_cb.findData(b_type)
                    if idx >= 0:
                        self.browser_cb.setCurrentIndex(idx)
                self.run_btn.setText("Resume")
            elif msg.clickedButton() == btn_new:
                clear_resume_state()
                self.log_message("Saved resume state cleared. Ready for a new run.")
                self.pending_resume_state = None
                self.run_btn.setText("Run")
            elif msg.clickedButton() == btn_discard:
                clear_resume_state()
                self.log_message("Saved resume state discarded.")
                self.pending_resume_state = None
                self.run_btn.setText("Run")

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Top menu bar
        top_bar_layout = QHBoxLayout()
        self.menu_btn = QToolButton()
        self.menu_btn.setText("☰")
        self.menu_btn.setToolTip("Menu")
        self.menu_btn.setAccessibleName("Menu")
        self.menu_btn.setFixedSize(30, 30)
        self.menu_btn.setPopupMode(QToolButton.InstantPopup)
        self.menu_btn.setStyleSheet("QToolButton::menu-indicator { image: none; width: 0px; }")

        menu = QMenu(self)

        action_update = QAction("Check for Updates", self)
        action_update.triggered.connect(
            lambda: self.update_manager.check_for_updates(is_manual=True)
        )
        menu.addAction(action_update)

        action_log = QAction("Open Log Folder", self)
        action_log.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(app_info.get_log_dir())))
        )
        menu.addAction(action_log)

        action_output_root = QAction("Open Output Root Folder", self)
        action_output_root.triggered.connect(self.open_output_root_folder)
        menu.addAction(action_output_root)

        action_output = QAction("Open Reports Folder", self)
        action_output.triggered.connect(self.open_output_folder)
        menu.addAction(action_output)

        menu.addSeparator()

        action_about = QAction("About", self)
        action_about.triggered.connect(lambda: show_about_dialog(self))
        menu.addAction(action_about)

        self.menu_btn.setMenu(menu)
        top_bar_layout.addWidget(self.menu_btn)
        top_bar_layout.addStretch()

        main_layout.addLayout(top_bar_layout)

        controls_group = QGroupBox("Configuration")
        form_layout = QFormLayout()

        self.mode_cb = QComboBox()
        self.mode_cb.addItems(["Scrape", "Report", "Full Pipeline"])
        self.mode_cb.currentTextChanged.connect(self.on_mode_changed)
        form_layout.addRow("Operation Mode:", self.mode_cb)

        self.start_date_input = QDateEdit()
        self.start_date_input.setCalendarPopup(True)
        self.start_date_input.setDisplayFormat("yyyyMMdd")
        self.start_date_input.setDate(QDate.currentDate())

        self.end_date_input = QDateEdit()
        self.end_date_input.setCalendarPopup(True)
        self.end_date_input.setDisplayFormat("yyyyMMdd")
        self.end_date_input.setDate(QDate.currentDate())

        date_range_widget = QWidget()
        date_range_layout = QHBoxLayout(date_range_widget)
        date_range_layout.setContentsMargins(0, 0, 0, 0)
        date_range_layout.addWidget(QLabel("Start"))
        date_range_layout.addWidget(self.start_date_input)
        date_range_layout.addSpacing(16)
        date_range_layout.addWidget(QLabel("End"))
        date_range_layout.addWidget(self.end_date_input)
        date_range_layout.addStretch()
        form_layout.addRow("Date:", date_range_widget)

        self.targets_cb = QComboBox()
        self.targets_cb.addItems(["image", "ocr", "all"])
        self.targets_cb.currentTextChanged.connect(self.on_mode_changed)
        form_layout.addRow("Targets:", self.targets_cb)

        self.report_mode_cb = QComboBox()
        self.report_mode_cb.addItems(["image", "ocr"])
        self.report_mode_cb.currentTextChanged.connect(self.on_mode_changed)
        form_layout.addRow("Report Mode:", self.report_mode_cb)

        self.config_dir_input, config_dir_row = self._create_path_row(
            "Config folder", self.config_dir, self.choose_config_dir
        )
        form_layout.addRow("Config:", config_dir_row)

        self.output_root_input, output_root_row = self._create_path_row(
            "Output folder", self.output_root, self.choose_output_root
        )
        form_layout.addRow("Output:", output_root_row)

        self.browser_cb = QComboBox()

        for b_type in ["Chrome", "Edge", "Firefox", "Chromium"]:
            display_name = get_browser_display_name(b_type)
            self.browser_cb.addItem(display_name, b_type.lower())
            if "(Not Installed)" in display_name:
                idx = self.browser_cb.count() - 1
                item = self.browser_cb.model().item(idx)
                if item is not None:
                    item.setEnabled(False)
        installed_idx = -1
        for i in range(self.browser_cb.count()):
            if "(Installed)" in self.browser_cb.itemText(i):
                installed_idx = i
                break
        self.browser_cb.setCurrentIndex(installed_idx if installed_idx >= 0 else 0)
        form_layout.addRow("Browser:", self.browser_cb)

        self.headless_cb = QCheckBox("Run browser headless")
        form_layout.addRow("", self.headless_cb)

        controls_group.setLayout(form_layout)
        main_layout.addWidget(controls_group)

        buttons_layout = QHBoxLayout()
        self.run_btn = QPushButton("Run")
        self.run_btn.clicked.connect(self.start_task)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self.pause_command)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_command)

        buttons_layout.addWidget(self.run_btn)
        buttons_layout.addWidget(self.pause_btn)
        buttons_layout.addWidget(self.stop_btn)
        main_layout.addLayout(buttons_layout)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        main_layout.addWidget(self.log_text)

        self.on_mode_changed(self.mode_cb.currentText())

    def _create_path_row(self, label: str, path: Path, chooser):
        path_input = QLineEdit(str(path))
        path_input.setReadOnly(True)
        path_input.setToolTip(str(path))
        path_input.setAccessibleName(label)
        browse_button = QPushButton("Browse...")
        browse_button.setAccessibleName(f"Browse {label}")
        browse_button.clicked.connect(chooser)
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(path_input)
        layout.addWidget(browse_button)
        return path_input, row

    def _set_path(self, setting_key: str, value: str, field: QLineEdit):
        selected = Path(value).expanduser().resolve()
        field.setText(str(selected))
        field.setToolTip(str(selected))
        self.settings.setValue(setting_key, str(selected))
        setattr(self, setting_key, selected)
        self.paths = get_output_paths(output_root=self.output_root)
        self.data_dir = self.paths.data_dir
        self.reports_dir = self.paths.reports_dir
        self.logs_dir = self.paths.logs_dir
        ensure_directories(output_root=self.output_root)

    def choose_output_root(self):
        selected = QFileDialog.getExistingDirectory(
            self, "Select Output Root folder", str(self.output_root)
        )
        if selected:
            self._set_path("output_root", selected, self.output_root_input)

    def choose_config_dir(self):
        selected = QFileDialog.getExistingDirectory(
            self, "Select config folder", str(self.config_dir)
        )
        if selected:
            self._set_path("config_dir", selected, self.config_dir_input)
            valid, missing_items = self.validate_config_files()
            if not valid:
                for item in missing_items:
                    self.log_message(f"[WARNING] Config file missing or incomplete: {item}")

    def get_selected_browser_type(self) -> str:
        data = self.browser_cb.currentData()
        if data is None:
            return self.browser_cb.currentText()
        return data

    def on_mode_changed(self, text=None):
        mode = self.mode_cb.currentText()
        if mode == "Scrape":
            self.targets_cb.setEnabled(True)
            self.report_mode_cb.setEnabled(False)
            self.browser_cb.setEnabled(True)
            self.headless_cb.setEnabled(True)
        elif mode == "Report":
            self.targets_cb.setEnabled(False)
            self.report_mode_cb.setEnabled(True)
            self.browser_cb.setEnabled(False)
            self.headless_cb.setEnabled(False)
        elif mode == "Full Pipeline":
            self.targets_cb.setEnabled(True)
            self.report_mode_cb.setEnabled(True)
            self.browser_cb.setEnabled(True)
            self.headless_cb.setEnabled(True)

    def log_message(self, message):
        self.log_text.append(message)
        self._check_for_incompleteness(message)

    def _check_for_incompleteness(self, message: str):
        if message.startswith(
            "[WARNING] Some data or screenshots are missing"
        ) or message.startswith("[WARNING] Incomplete"):
            return

        # Scrape summary check
        scrape_summary = re.search(r"SUMMARY:\s*(\d+)\s*OK,\s*(\d+)\s*N/A,\s*(\d+)\s*FAIL", message)
        if scrape_summary:
            na_cnt = int(scrape_summary.group(2))
            fail_cnt = int(scrape_summary.group(3))
            if na_cnt > 0 or fail_cnt > 0:
                self.has_incomplete_data = True
                warn = (
                    f"[WARNING] Some data or screenshots are missing or incomplete in scrape "
                    f"(N/A: {na_cnt}, FAIL: {fail_cnt})."
                )
                self.log_text.append(warn)
                return

        # REQ-33: match format_summary_table() output
        # "OCR Summary: OK=<n> | Partial=<n> | Fail=<n>"
        ocr_sum = re.search(r"OCR Summary:.*?Partial=(\d+)\s*\|\s*Fail=(\d+)", message)
        if ocr_sum:
            partial_cnt = int(ocr_sum.group(1))
            fail_cnt = int(ocr_sum.group(2))
            if partial_cnt > 0 or fail_cnt > 0:
                self.has_incomplete_data = True
                self.log_text.append(
                    f"[WARNING] Some data or screenshots are missing or incomplete in report "
                    f"(Partial: {partial_cnt}, Fail: {fail_cnt})."
                )
                return

        # "Image inserted: <n> | Missing: <n>"
        img_missing = re.search(r"Image inserted:.*?Missing:\s*(\d+)", message)
        if img_missing:
            cnt = int(img_missing.group(1))
            if cnt > 0:
                self.has_incomplete_data = True
                self.log_text.append(
                    f"[WARNING] Some data or screenshots are missing in report ({cnt} missing screenshot(s))."
                )
                return

        # Missing screenshots line in report
        missing_sc = re.search(r"Missing screenshots:\s*([1-9]\d*)", message)
        if missing_sc:
            cnt = int(missing_sc.group(1))
            self.has_incomplete_data = True
            self.log_text.append(
                f"[WARNING] Some data or screenshots are missing in report ({cnt} missing screenshot(s))."
            )
            return

        # Missing mappings line in report
        missing_map = re.search(r"Missing mappings\s*:\s*([1-9]\d*)", message)
        if missing_map:
            cnt = int(missing_map.group(1))
            self.has_incomplete_data = True
            self.log_text.append(
                f"[WARNING] Some data or screenshots are missing in report ({cnt} missing mapping(s))."
            )
            return

        # Failed inserts in report
        failed_ins = re.search(r"Failed inserts\s*:\s*([1-9]\d*)", message)
        if failed_ins:
            cnt = int(failed_ins.group(1))
            self.has_incomplete_data = True
            self.log_text.append(
                f"[WARNING] Some data or screenshots are missing in report ({cnt} failed insert(s))."
            )
            return

        # OCR Fail in report (legacy individual indicator)
        ocr_fail = re.search(r"OCR Fail\s*:\s*([1-9]\d*)", message)
        if ocr_fail:
            cnt = int(ocr_fail.group(1))
            self.has_incomplete_data = True
            self.log_text.append(
                f"[WARNING] Some data or screenshots are missing or incomplete in report ({cnt} OCR fail(s))."
            )
            return

        # OCR Partial in report (legacy individual indicator)
        ocr_part = re.search(r"OCR Partial\s*:\s*([1-9]\d*)", message)
        if ocr_part:
            cnt = int(ocr_part.group(1))
            self.has_incomplete_data = True
            self.log_text.append(
                f"[WARNING] Some data or screenshots are missing or incomplete in report ({cnt} OCR partial(s))."
            )
            return

        # Individual indicators
        if (
            "error=missing_screenshot" in message
            or "[!] N/A - Grafik belum ter-generate" in message
        ):
            self.has_incomplete_data = True
            if not self._warned_incomplete_item:
                self._warned_incomplete_item = True
                self.log_text.append(
                    "[WARNING] Some data or screenshots are missing or incomplete."
                )

    def get_completion_target_folder(self) -> Path:
        mode = self.mode_cb.currentText()
        if mode in ("Report", "Full Pipeline"):
            return self.paths.reports_dir if self.paths.reports_dir.exists() else self.output_root
        else:  # "Scrape"
            return self.paths.data_dir if self.paths.data_dir.exists() else self.output_root

    def create_completion_dialog(self, exit_code: int) -> QMessageBox:
        msg_box = QMessageBox(self)
        if exit_code == 0:
            if self.has_incomplete_data:
                msg_box.setWindowTitle("Task Finished with Warnings")
                msg_box.setText(
                    "Task finished with warnings.\n"
                    "Some items may be incomplete or failed.\n"
                    "Would you like to open the output folder to inspect?"
                )
                msg_box.setIcon(QMessageBox.Icon.Warning)
            else:
                msg_box.setWindowTitle("Task Completed")
                msg_box.setText(
                    "Task finished successfully.\nWould you like to open the output folder?"
                )
                msg_box.setIcon(QMessageBox.Icon.Information)
        else:
            msg_box.setWindowTitle("Task Finished with Warnings / Errors")
            msg_box.setText(
                f"Task finished with exit code {exit_code}.\n"
                "Some items may be incomplete or failed.\n"
                "Would you like to open the output folder to inspect?"
            )
            msg_box.setIcon(QMessageBox.Icon.Warning)

        open_btn = msg_box.addButton("Open Output Folder", QMessageBox.ButtonRole.ActionRole)
        msg_box.addButton("Close", QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(open_btn)
        return msg_box

    def open_output_root_folder(self):
        try:
            self.output_root.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(self.output_root))
            else:
                subprocess.Popen(["xdg-open", str(self.output_root)])
        except Exception as e:
            self.log_message(f"Could not open output root folder: {e}")

    def open_output_folder(self):
        try:
            self.reports_dir.mkdir(parents=True, exist_ok=True)
            if os.name == "nt":
                os.startfile(str(self.reports_dir))
            else:
                subprocess.Popen(["xdg-open", str(self.reports_dir)])
        except Exception as e:
            self.log_message(f"Could not open output folder: {e}")

    def pause_command(self):
        if self.worker is None:
            return
        if self.pause_btn.text() == "Pause":
            self.worker.pause_event.set()
            self.pause_btn.setText("Continue")
            self.log_message("Paused — will finish current item then wait.")
        else:
            self.worker.pause_event.clear()
            self.pause_btn.setText("Pause")
            self.log_message("Resumed.")

    def stop_command(self):
        if self.worker:
            self.worker.request_stop()
            self.stop_btn.setEnabled(False)
            self.pause_btn.setEnabled(False)
            state = load_resume_state()
            if state:
                state["status"] = "stopped"
                save_resume_state(state)

    def validate_date_inputs(self, date_mode, d_str, s_str, e_str):
        if date_mode == "Date Range":
            if e_str < s_str:
                return False, "End date cannot be before start date.", self.end_date_input
        return True, "", None

    def validate_config_files(self) -> tuple[bool, list[str]]:
        mode = self.mode_cb.currentText()
        config_dir = Path(self.config_dir)
        missing_items: list[str] = []

        # a. list_mrtg_targets.csv: Required for Scrape, Report, Full Pipeline
        if mode in ("Scrape", "Report", "Full Pipeline"):
            targets_file = config_dir / "list_mrtg_targets.csv"
            if not targets_file.exists():
                missing_items.append("list_mrtg_targets.csv")

        # b. If mode is "Report" or "Full Pipeline"
        if mode in ("Report", "Full Pipeline"):
            report_mode = self.report_mode_cb.currentText()
            if report_mode == "ocr":
                template_file = (
                    config_dir
                    / "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx"
                )
                if not template_file.exists():
                    missing_items.append(
                        "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx"
                    )

                pos_file = config_dir / "list_mrtg_data_position.txt"
                pos_example = config_dir / "list_mrtg_data_position.example.txt"
                if not pos_file.exists() and not pos_example.exists():
                    missing_items.append("list_mrtg_data_position.txt")
            else:  # "image"
                template_file = (
                    config_dir
                    / "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx"
                )
                if not template_file.exists():
                    missing_items.append(
                        "MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom (Img only).xlsx"
                    )

                pos_file = config_dir / "list_mrtg_data_position_img_only.txt"
                pos_example = config_dir / "list_mrtg_data_position_img_only.example.txt"
                if not pos_file.exists() and not pos_example.exists():
                    missing_items.append("list_mrtg_data_position_img_only.txt")

        # c. If mode is "Scrape" or "Full Pipeline"
        if mode in ("Scrape", "Full Pipeline"):
            env_file = config_dir / ".env"
            env_exists = env_file.exists()
            if not env_exists:
                missing_items.append(".env")

            env_vals = dotenv_values(env_file) if env_exists else {}

            def _get_val(key: str) -> str:
                if env_exists and key in env_vals:
                    val = env_vals[key]
                    return str(val).strip() if val is not None else ""
                return os.getenv(key, "").strip()

            auto_login_enabled = _get_val("AUTO_LOGIN_ENABLED").lower() in (
                "true",
                "1",
                "yes",
            )
            if auto_login_enabled:
                user = _get_val("TELKOM_USER")
                pwd = _get_val("TELKOM_PASSWORD")
                if not user or not pwd:
                    missing_items.append(
                        ".env (auto-login enabled but TELKOM_USER or TELKOM_PASSWORD missing)"
                    )

        return len(missing_items) == 0, missing_items

    def start_task(self):
        valid, missing_items = self.validate_config_files()
        if not valid:
            for item in missing_items:
                self.log_message(f"[WARNING] Config file missing or incomplete: {item}")
            QMessageBox.warning(
                self,
                "Missing Configuration Files",
                "The following configuration files are missing or incomplete in your config folder:\n\n"
                + "\n".join(f"• {m}" for m in missing_items)
                + "\n\nPlease check your config directory before running.",
            )
            return

        s_str = self.start_date_input.date().toString("yyyyMMdd")
        e_str = self.end_date_input.date().toString("yyyyMMdd")

        if s_str == e_str:
            date_mode = "Single Date"
            d_str = s_str
            start_date_str = ""
            end_date_str = ""
        else:
            date_mode = "Date Range"
            d_str = ""
            start_date_str = s_str
            end_date_str = e_str

        ok, msg, field = self.validate_date_inputs(date_mode, d_str, start_date_str, end_date_str)
        if not ok:
            self.log_message(f"[FAIL] {msg}")
            QMessageBox.warning(self, "Invalid Date", msg)
            if field:
                field.setFocus()
            return

        self.run_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.pause_btn.setText("Pause")
        self.stop_btn.setEnabled(True)
        self.has_incomplete_data = False
        self._warned_incomplete_item = False
        self.log_message("--- Starting Task ---")

        if self.pending_resume_state:
            state = self.pending_resume_state
            state["status"] = "running"
            state["resume_mode"] = True
            save_resume_state(state)
            self.run_btn.setText("Run")
            resume_state = state
            resume_mode = True
            self.pending_resume_state = None
        else:
            mode_val = self.mode_cb.currentText()
            phase = (
                "scrape_sid"
                if mode_val in ("Scrape", "Full Pipeline")
                else (
                    "report_image" if self.report_mode_cb.currentText() == "image" else "report_ocr"
                )
            )

            dates_for_state = [d_str] if date_mode == "Single Date" else [s_str, e_str]

            state = {
                "version": 1,
                "status": "running",
                "operation_mode": mode_val,
                "date_mode": date_mode,
                "date_str": d_str,
                "start_date_str": start_date_str,
                "end_date_str": end_date_str,
                "dates": dates_for_state,
                "targets_filter": self.targets_cb.currentText(),
                "report_mode": self.report_mode_cb.currentText(),
                "browser_type": self.get_selected_browser_type(),
                "config_dir": str(self.config_dir),
                "output_dir": str(self.output_root),
                "data_dir": str(self.data_dir),
                "reports_dir": str(self.reports_dir),
                "current_phase": phase,
                "total_items": 0,
                "completed_items_count": 0,
                "last_completed": None,
                "next_item": None,
                "completed_items": [],
            }
            state["resume_mode"] = False
            save_resume_state(state)
            resume_state = state
            resume_mode = False

        self.worker_thread = QThread()
        self.worker = Worker(
            mode=self.mode_cb.currentText(),
            date_mode=date_mode,
            date_str=d_str,
            start_date_str=start_date_str,
            end_date_str=end_date_str,
            targets=self.targets_cb.currentText(),
            report_mode=self.report_mode_cb.currentText(),
            headless=self.headless_cb.isChecked(),
            browser_type=self.get_selected_browser_type(),
            resume_state=resume_state,
            resume_mode=resume_mode,
            output_dir=self.output_root,
            data_dir=self.data_dir,
            config_dir=self.config_dir,
            reports_dir=self.reports_dir,
        )
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.log_signal.connect(self.log_message)
        self.worker.finished_signal.connect(self.on_worker_finished)

        self.worker.finished_signal.connect(self.worker_thread.quit)
        self.worker.finished_signal.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()

    def run_command(self):
        self.start_task()

    def on_worker_finished(self, exit_code):
        if exit_code == 130:
            self.log_message("--- Task Stopped by User ---")
            state = load_resume_state()
            if state:
                state["status"] = "stopped"
                save_resume_state(state)
        elif exit_code == 0:
            self.log_message(f"--- Task Finished (Exit code: {exit_code}) ---")
            clear_resume_state()
        else:
            self.log_message(f"--- Task Finished (Exit code: {exit_code}) ---")
            state = load_resume_state()
            if state:
                state["status"] = "stopped"
                save_resume_state(state)

        self.run_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("Pause")
        self.stop_btn.setEnabled(False)

        msg_box = self.create_completion_dialog(exit_code)
        msg_box.exec()
        clicked = msg_box.clickedButton()
        if clicked and clicked.text() == "Open Output Folder":
            target_folder = self.get_completion_target_folder()
            try:
                target_folder.mkdir(parents=True, exist_ok=True)
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(target_folder)))
            except Exception as e:
                self.log_message(f"Could not open output folder: {e}")

    def closeEvent(self, event):
        try:
            if getattr(self, "worker", None) is not None:
                try:
                    self.worker.request_stop()
                except RuntimeError:
                    pass
            thread = getattr(self, "worker_thread", None)
            if thread is not None:
                try:
                    if thread.isRunning():
                        thread.quit()
                        if not thread.wait(2000):
                            # REQ-34: worker still running — defer close, do NOT accept
                            event.ignore()
                            self.setWindowTitle("Stopping worker… please wait")
                            self.log_text.append(
                                "[STATUS] Worker still finishing; window will close shortly."
                            )
                            thread.finished.connect(self.close)
                            return
                except RuntimeError:
                    pass
        finally:
            self.worker = None
            self.worker_thread = None
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
