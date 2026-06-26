from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt
from mrtg_automation import app_info

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {app_info.APP_NAME}")
        self.setFixedSize(400, 300)

        layout = QVBoxLayout(self)
        title_label = QLabel(f"<b>{app_info.APP_NAME}</b>")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        version_label = QLabel(f"Version: {app_info.APP_VERSION}")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)

        build_label = QLabel(f"Build Date: {app_info.APP_BUILD_DATE}")
        build_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(build_label)

        desc_label = QLabel("Automation tool for scraping MRTG screenshots from TelkomCare and generating Excel reports.")
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc_label)

        deps_label = QLabel("Dependencies:\nPython\nPySide6\nSelenium\nOpenPyXL\nTesseract/OCR")
        deps_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(deps_label)

        links_label = QLabel(f"<a href='https://github.com/{app_info.GITHUB_REPO}'>GitHub</a> | <a href='{app_info.RELEASES_URL}'>Releases</a>")
        links_label.setOpenExternalLinks(True)
        links_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(links_label)

        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)

def show_about_dialog(parent=None):
    dialog = AboutDialog(parent)
    dialog.exec()
