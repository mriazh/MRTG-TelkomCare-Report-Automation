import json
import urllib.request
import urllib.error
from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool
from PySide6.QtWidgets import QMessageBox, QProgressDialog
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from mrtg_automation import app_info

def parse_version(version_str):
    # Remove 'v' prefix if present
    if version_str.startswith('v'):
        version_str = version_str[1:]
    try:
        parts = version_str.split('-')[0].split('.')
        return tuple(map(int, parts))
    except (ValueError, AttributeError):
        return (0, 0, 0)

def is_newer_version(latest_str, current_str):
    return parse_version(latest_str) > parse_version(current_str)

def map_network_error(err_msg):
    if "404" in err_msg:
        return "Release not found (404). The repository might not have any releases yet."
    if "403" in err_msg:
        return "API rate limit exceeded or access denied (403)."
    return err_msg

class UpdateCheckSignals(QObject):
    finished = Signal(dict)
    error = Signal(str)

class UpdateCheckWorker(QRunnable):
    def __init__(self, is_manual=False):
        super().__init__()
        self.is_manual = is_manual
        self.signals = UpdateCheckSignals()

    def run(self):
        try:
            req = urllib.request.Request(
                app_info.LATEST_RELEASE_API,
                headers={'User-Agent': 'MRTG-TelkomCare-Updater'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

                latest_version = data.get('tag_name', '')
                if not latest_version:
                    raise ValueError("Could not find tag_name in release data")

                body = data.get('body', '')
                html_url = data.get('html_url', '')
                if not html_url:
                    html_url = app_info.RELEASES_URL

                self.signals.finished.emit({
                    'latest_version': latest_version,
                    'release_notes': body,
                    'release_url': html_url,
                    'is_manual': self.is_manual
                })
        except urllib.error.URLError as e:
            self.signals.error.emit(map_network_error(str(e)))
        except Exception as e:
            self.signals.error.emit(str(e))

class UpdateManager(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.thread_pool = QThreadPool.globalInstance()
        self._progress_dialog = None
        self._check_in_progress = False
        self._worker = None

    def _cleanup(self):
        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
        self._check_in_progress = False
        self._worker = None

    def check_for_updates(self, is_manual=False):
        if self._check_in_progress:
            if is_manual:
                QMessageBox.information(self.parent_widget, "Update Check", "An update check is already running.")
            return

        self._check_in_progress = True

        if is_manual:
            self._progress_dialog = QProgressDialog("Checking for updates...", "", 0, 0, self.parent_widget)
            self._progress_dialog.setWindowTitle("Update Check")
            self._progress_dialog.setCancelButton(None)
            self._progress_dialog.setModal(True)
            self._progress_dialog.show()

        self._worker = UpdateCheckWorker(is_manual=is_manual)
        self._worker.signals.finished.connect(self._on_check_finished)
        self._worker.signals.error.connect(self._on_check_error)
        self.thread_pool.start(self._worker)

    def _on_check_finished(self, result):
        self._cleanup()

        latest_version = result['latest_version']
        is_manual = result['is_manual']

        if is_newer_version(latest_version, app_info.APP_VERSION):
            notes = result['release_notes']
            if len(notes) > 1500:
                notes = notes[:1500] + "...\n(Truncated)"

            msg = QMessageBox(self.parent_widget)
            msg.setWindowTitle("Update Available")
            msg.setText(f"A new version of {app_info.APP_NAME} is available!")
            msg.setInformativeText(f"Current version: {app_info.APP_VERSION}\nLatest version: {latest_version}\n\nRelease Notes:\n{notes}")

            btn_view = msg.addButton("View Release", QMessageBox.ActionRole)
            btn_later = msg.addButton("Later", QMessageBox.RejectRole)

            msg.exec()

            if msg.clickedButton() == btn_view:
                QDesktopServices.openUrl(QUrl(result['release_url']))
        elif is_manual:
            QMessageBox.information(
                self.parent_widget,
                "Up to Date",
                f"You are running the latest version ({app_info.APP_VERSION})."
            )

    def _on_check_error(self, error_msg):
        self._cleanup()

        # Only show errors for manual checks
        QMessageBox.warning(
            self.parent_widget,
            "Update Check Failed",
            f"Could not check for updates:\n{error_msg}"
        )
