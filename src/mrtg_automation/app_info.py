from .shared.paths import LOGS_DIR

APP_NAME = "MRTG TelkomCare Report Automation"
APP_VERSION = "0.1.0"
APP_BUILD_DATE = "2026"
GITHUB_REPO = "mriazh/MRTG-TelkomCare-Report-Automation"
RELEASES_URL = "https://github.com/mriazh/MRTG-TelkomCare-Report-Automation/releases"
LATEST_RELEASE_API = "https://api.github.com/repos/mriazh/MRTG-TelkomCare-Report-Automation/releases/latest"
INSTALLER_ASSET_PREFIX = "MRTG-TelkomCare-Setup"
INSTALLER_ASSET_SUFFIX = ".exe"

def get_log_dir():
    return LOGS_DIR
