import contextlib
import io
import logging
import os
import sys
import threading

from PySide6.QtCore import QDate, QObject, QThread, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
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
from mrtg_automation.shared.paths import REPORTS_DIR, ROOT_DIR, ensure_directories
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

    def __init__(self, mode, date_mode, date_str, start_date_str, end_date_str,
                 targets, report_mode, headless, browser_type="auto", resume_state=None, resume_mode=False):
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
        self.cancel_event = threading.Event()
        self.pause_event = threading.Event()

    def request_stop(self):
        self.cancel_event.set()
        self.pause_event.clear()
        try:
            self.log_signal.emit("Stop requested. Cancelling startup/login or waiting for current item to finish...")
        except RuntimeError:
            pass  # Ignore if Qt window/signal source is destroyed during app close

    def run(self):
        def _is_stacktrace_noise(line: str) -> bool:
            """Check if a single line is Selenium/OS stacktrace noise to be skipped."""
            stripped = line.strip()
            if not stripped:
                return True
            noise_markers = [
                "Stacktrace:", "Chromedriver!", "(Session info:",
                "For documentation on this error", "Build info:",
                "System info:", "Driver info:", "KERNEL32!", "Ntdll!",
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
                    cfg = Config()
                    effective = getattr(cfg, 'effective_browser_type', getattr(cfg, 'browser_type', 'chrome'))
                    self.log_signal.emit(f"Browser configuration: {cfg.browser_type} (effective: {effective})")

                if self.date_mode == "Single Date":
                    self.log_signal.emit(f"Date: {self.date_str}")
                else:
                    self.log_signal.emit(f"Date range: {self.start_date_str} to {self.end_date_str}")

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
                        resume_mode=self.resume_mode
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
                        resume_mode=self.resume_mode
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
                        resume_mode=self.resume_mode
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

        ensure_directories()

        self.worker_thread = None
        self.worker = None
        self.pending_resume_state = None
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
            msg.setText("An unfinished run was found. What would you like to do?\n\n" + format_resume_summary(state))
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
        action_update.triggered.connect(lambda: self.update_manager.check_for_updates(is_manual=True))
        menu.addAction(action_update)

        action_log = QAction("Open Log Folder", self)
        action_log.triggered.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(app_info.get_log_dir()))))
        menu.addAction(action_log)

        action_output = QAction("Open Output Folder", self)
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
        form_layout.addRow("Targets:", self.targets_cb)

        self.report_mode_cb = QComboBox()
        self.report_mode_cb.addItems(["image", "ocr"])
        form_layout.addRow("Report Mode:", self.report_mode_cb)

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
        self.run_btn.clicked.connect(self.run_command)

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

    def get_selected_browser_type(self) -> str:
        data = self.browser_cb.currentData()
        if data is None:
            return self.browser_cb.currentText()
        return data

    def on_mode_changed(self, text):
        if text == "Scrape":
            self.targets_cb.setEnabled(True)
            self.report_mode_cb.setEnabled(False)
            self.browser_cb.setEnabled(True)
            self.headless_cb.setEnabled(True)
        elif text == "Report":
            self.targets_cb.setEnabled(False)
            self.report_mode_cb.setEnabled(True)
            self.browser_cb.setEnabled(False)
            self.headless_cb.setEnabled(False)
        elif text == "Full Pipeline":
            self.targets_cb.setEnabled(True)
            self.report_mode_cb.setEnabled(True)
            self.browser_cb.setEnabled(True)
            self.headless_cb.setEnabled(True)

    def log_message(self, message):
        self.log_text.append(message)

    def open_output_folder(self):
        try:
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            os.startfile(str(REPORTS_DIR))
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

    def run_command(self):
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
            phase = "scrape_sid" if mode_val in ("Scrape", "Full Pipeline") else ("report_image" if self.report_mode_cb.currentText() == "image" else "report_ocr")

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
                "current_phase": phase,
                "total_items": 0,
                "completed_items_count": 0,
                "last_completed": None,
                "next_item": None,
                "completed_items": []
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
            resume_mode=resume_mode
        )
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.log_signal.connect(self.log_message)
        self.worker.finished_signal.connect(self.on_worker_finished)

        self.worker.finished_signal.connect(self.worker_thread.quit)
        self.worker.finished_signal.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)

        self.worker_thread.start()

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
                        if not thread.wait(15000):
                            thread.terminate()
                            thread.wait(3000)
                except RuntimeError:
                    pass  # C++ object already deleted
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
