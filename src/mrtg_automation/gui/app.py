import sys
import os
import io
import contextlib
import threading

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QLineEdit, QCheckBox, QPushButton, QTextEdit,
    QFormLayout, QGroupBox, QMessageBox
)
from PySide6.QtCore import QThread, Signal, QObject

from mrtg_automation.cli import run_scrape_command, run_report_command, run_full_command
from mrtg_automation.shared.paths import REPORTS_DIR
from mrtg_automation.shared.resume_state import (
    load_resume_state, save_resume_state, clear_resume_state,
    has_unfinished_resume_state, format_resume_summary
)

class Worker(QObject):
    log_signal = Signal(str)
    finished_signal = Signal(int)
    manual_login_required = Signal()

    def __init__(self, mode, date_mode, date_str, start_date_str, end_date_str,
                 targets, report_mode, headless, resume_state=None, resume_mode=False):
        super().__init__()
        self.mode = mode
        self.date_mode = date_mode
        self.date_str = date_str
        self.start_date_str = start_date_str
        self.end_date_str = end_date_str
        self.targets = targets
        self.report_mode = report_mode
        self.headless = headless
        self.resume_state = resume_state
        self.resume_mode = resume_mode
        self.login_event = threading.Event()
        self.cancel_event = threading.Event()

    def request_stop(self):
        self.cancel_event.set()
        self.login_event.set()
        self.log_signal.emit("Stop requested. Waiting for current item to finish...")

    def wait_for_manual_login_gui(self):
        self.log_signal.emit("MANUAL LOGIN REQUIRED")
        self.log_signal.emit("Complete captcha/MFA in the opened browser, then click 'Continue After Login' in the GUI.")
        self.login_event.clear()
        self.manual_login_required.emit()

        while not self.cancel_event.is_set():
            if self.login_event.wait(0.2):
                break

    def run(self):
        class StreamRedirector(io.StringIO):
            def __init__(self, signal):
                super().__init__()
                self.signal = signal

            def write(self, text):
                if text.strip():
                    self.signal.emit(text.strip())
                super().write(text)

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
                        manual_login_waiter=self.wait_for_manual_login_gui,
                        cancel_event=self.cancel_event,
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
                        manual_login_waiter=self.wait_for_manual_login_gui,
                        cancel_event=self.cancel_event,
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

        self.worker_thread = None
        self.worker = None
        self.pending_resume_state = None

        self.setup_ui()
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
                self.date_mode_cb.setCurrentText(state.get("date_mode", "Single Date"))
                if state.get("date_str"):
                    self.single_date_input.setText(state.get("date_str"))
                if state.get("start_date_str"):
                    self.start_date_input.setText(state.get("start_date_str"))
                if state.get("end_date_str"):
                    self.end_date_input.setText(state.get("end_date_str"))
                self.targets_cb.setCurrentText(state.get("targets_filter", "image"))
                self.report_mode_cb.setCurrentText(state.get("report_mode", "image"))
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

        controls_group = QGroupBox("Configuration")
        form_layout = QFormLayout()

        self.mode_cb = QComboBox()
        self.mode_cb.addItems(["Scrape", "Report", "Full Pipeline"])
        self.mode_cb.currentTextChanged.connect(self.on_mode_changed)
        form_layout.addRow("Operation Mode:", self.mode_cb)

        self.date_mode_cb = QComboBox()
        self.date_mode_cb.addItems(["Single Date", "Date Range"])
        self.date_mode_cb.currentTextChanged.connect(self.on_date_mode_changed)
        form_layout.addRow("Date Mode:", self.date_mode_cb)

        self.single_date_input = QLineEdit()
        self.single_date_input.setPlaceholderText("YYYYMMDD")
        form_layout.addRow("Single Date:", self.single_date_input)

        self.start_date_input = QLineEdit()
        self.start_date_input.setPlaceholderText("YYYYMMDD")
        form_layout.addRow("Start Date:", self.start_date_input)

        self.end_date_input = QLineEdit()
        self.end_date_input.setPlaceholderText("YYYYMMDD")
        form_layout.addRow("End Date:", self.end_date_input)

        self.targets_cb = QComboBox()
        self.targets_cb.addItems(["image", "ocr", "all"])
        form_layout.addRow("Targets:", self.targets_cb)

        self.report_mode_cb = QComboBox()
        self.report_mode_cb.addItems(["image", "ocr"])
        form_layout.addRow("Report Mode:", self.report_mode_cb)

        self.headless_cb = QCheckBox("Run Chrome headless")
        form_layout.addRow("", self.headless_cb)

        controls_group.setLayout(form_layout)
        main_layout.addWidget(controls_group)

        buttons_layout = QHBoxLayout()
        self.run_btn = QPushButton("Run")
        self.run_btn.clicked.connect(self.run_command)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_command)

        self.continue_login_btn = QPushButton("Continue After Login")
        self.continue_login_btn.setEnabled(False)
        self.continue_login_btn.clicked.connect(self.continue_after_login)

        self.clear_log_btn = QPushButton("Clear Log")
        self.clear_log_btn.clicked.connect(self.clear_log)

        self.open_output_btn = QPushButton("Open Output Folder")
        self.open_output_btn.clicked.connect(self.open_output_folder)

        buttons_layout.addWidget(self.run_btn)
        buttons_layout.addWidget(self.stop_btn)
        buttons_layout.addWidget(self.continue_login_btn)
        buttons_layout.addWidget(self.clear_log_btn)
        buttons_layout.addWidget(self.open_output_btn)
        main_layout.addLayout(buttons_layout)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        main_layout.addWidget(self.log_text)

        self.on_date_mode_changed(self.date_mode_cb.currentText())
        self.on_mode_changed(self.mode_cb.currentText())

    def on_date_mode_changed(self, text):
        if text == "Single Date":
            self.single_date_input.setEnabled(True)
            self.start_date_input.setEnabled(False)
            self.end_date_input.setEnabled(False)
        else:
            self.single_date_input.setEnabled(False)
            self.start_date_input.setEnabled(True)
            self.end_date_input.setEnabled(True)

    def on_mode_changed(self, text):
        if text == "Scrape":
            self.targets_cb.setEnabled(True)
            self.report_mode_cb.setEnabled(False)
        elif text == "Report":
            self.targets_cb.setEnabled(False)
            self.report_mode_cb.setEnabled(True)
        elif text == "Full Pipeline":
            self.targets_cb.setEnabled(True)
            self.report_mode_cb.setEnabled(True)

    def log_message(self, message):
        self.log_text.append(message)

    def clear_log(self):
        self.log_text.clear()

    def open_output_folder(self):
        try:
            os.startfile(REPORTS_DIR)
        except Exception as e:
            self.log_message(f"Could not open output folder: {e}")

    def continue_after_login(self):
        if self.worker:
            self.log_message("Continuing after manual login...")
            self.worker.login_event.set()
            self.continue_login_btn.setEnabled(False)

    def stop_command(self):
        if self.worker:
            self.worker.request_stop()
            self.stop_btn.setEnabled(False)
            state = load_resume_state()
            if state:
                state["status"] = "stopped"
                save_resume_state(state)

    def run_command(self):
        date_mode = self.date_mode_cb.currentText()
        d_str = self.single_date_input.text().strip()
        s_str = self.start_date_input.text().strip()
        e_str = self.end_date_input.text().strip()

        if date_mode == "Single Date" and not d_str:
            self.log_message("[FAIL] Single date is required.")
            return
        if date_mode == "Date Range" and (not s_str or not e_str):
            self.log_message("[FAIL] Both start and end dates are required.")
            return

        self.run_btn.setEnabled(False)
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
                "start_date_str": s_str,
                "end_date_str": e_str,
                "dates": dates_for_state,
                "targets_filter": self.targets_cb.currentText(),
                "report_mode": self.report_mode_cb.currentText(),
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
            start_date_str=s_str,
            end_date_str=e_str,
            targets=self.targets_cb.currentText(),
            report_mode=self.report_mode_cb.currentText(),
            headless=self.headless_cb.isChecked(),
            resume_state=resume_state,
            resume_mode=resume_mode
        )
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.log_signal.connect(self.log_message)
        self.worker.finished_signal.connect(self.on_worker_finished)
        self.worker.manual_login_required.connect(lambda: self.continue_login_btn.setEnabled(True))

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
        self.stop_btn.setEnabled(False)
        self.continue_login_btn.setEnabled(False)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
