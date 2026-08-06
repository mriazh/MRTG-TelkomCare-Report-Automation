"""
Browser auto-detection helper module for MRTG TelkomCare Automation.

Detects installed browsers (Chrome, Edge, Firefox, Chromium) across Windows, Linux, and macOS.
"""

import logging
import os
import shutil
import sys

logger = logging.getLogger("mrtg_automation.shared.browser_detection")

SUPPORTED_BROWSERS = ["chrome", "edge", "firefox", "chromium"]
PREFERENCE_ORDER = ["chrome", "edge", "firefox", "chromium"]

# Binary names for shutil.which
BINARY_NAMES = {
    "chrome": [
        "chrome",
        "google-chrome",
        "google-chrome-stable",
        "chrome.exe",
        "google-chrome.exe",
    ],
    "edge": ["msedge", "microsoft-edge", "microsoft-edge-stable", "msedge.exe"],
    "firefox": ["firefox", "firefox.exe"],
    "chromium": ["chromium", "chromium-browser", "chromium.exe"],
}

# Standard OS installation paths
STANDARD_PATHS = {
    "win32": {
        "chrome": [
            r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe",
            r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe",
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
        ],
        "edge": [
            r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe",
            r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe",
            r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe",
        ],
        "firefox": [
            r"%PROGRAMFILES%\Mozilla Firefox\firefox.exe",
            r"%PROGRAMFILES(X86)%\Mozilla Firefox\firefox.exe",
            r"%LOCALAPPDATA%\Mozilla Firefox\firefox.exe",
        ],
        "chromium": [
            r"%LOCALAPPDATA%\Chromium\Application\chromium.exe",
            r"%PROGRAMFILES%\Chromium\Application\chromium.exe",
        ],
    },
    "darwin": {
        "chrome": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
        "edge": ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"],
        "firefox": ["/Applications/Firefox.app/Contents/MacOS/firefox"],
        "chromium": ["/Applications/Chromium.app/Contents/MacOS/Chromium"],
    },
    "linux": {
        "chrome": ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chrome"],
        "edge": ["/usr/bin/microsoft-edge", "/usr/bin/microsoft-edge-stable", "/usr/bin/msedge"],
        "firefox": ["/usr/bin/firefox"],
        "chromium": ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/snap/bin/chromium"],
    },
}


def _check_windows_registry(app_name: str) -> str | None:
    """Query Windows Registry for app binary path if on Windows."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:
        return None

    keys = [
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\\" + app_name,
        ),
        (
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\\" + app_name,
        ),
    ]
    for root_key, subkey in keys:
        try:
            with winreg.OpenKey(root_key, subkey) as key:
                val, _ = winreg.QueryValueEx(key, "")
                if val and os.path.isfile(val):
                    return val
        except OSError:
            continue
    return None


def find_browser_binary(browser_type: str) -> str | None:
    """Find executable binary path for a given browser type.

    Args:
        browser_type: 'chrome', 'edge', 'firefox', or 'chromium'

    Returns:
        String path to executable binary, or None if not found on disk.
    """
    browser_type = browser_type.lower().strip()
    if browser_type not in SUPPORTED_BROWSERS:
        return None

    # 1. Check PATH via shutil.which
    for name in BINARY_NAMES.get(browser_type, []):
        which_path = shutil.which(name)
        if which_path and os.path.isfile(which_path):
            return which_path

    # 2. Check platform standard paths
    plat = (
        "win32" if sys.platform == "win32" else ("darwin" if sys.platform == "darwin" else "linux")
    )
    paths = STANDARD_PATHS.get(plat, {}).get(browser_type, [])
    for p in paths:
        expanded = os.path.expandvars(p)
        if os.path.isfile(expanded):
            return expanded

    # 3. Check Windows registry as fallback on Windows
    if sys.platform == "win32":
        app_names = {
            "chrome": "chrome.exe",
            "edge": "msedge.exe",
            "firefox": "firefox.exe",
            "chromium": "chromium.exe",
        }
        reg_path = _check_windows_registry(app_names.get(browser_type, ""))
        if reg_path:
            return reg_path

    return None


def detect_installed_browsers() -> dict[str, str]:
    """Scan system for all installed supported browsers.

    Returns:
        Dict mapping browser_type ('chrome', 'edge', 'firefox', 'chromium')
        to executable binary path.
    """
    detected = {}
    for b_type in SUPPORTED_BROWSERS:
        binary = find_browser_binary(b_type)
        if binary:
            detected[b_type] = binary
    return detected


def get_browser_display_name(browser_type: str) -> str:
    """Return display name with installation status for combo box items.

    Args:
        browser_type: 'chrome', 'edge', 'firefox', or 'chromium'

    Returns:
        String like 'Chrome (Installed)' or 'Firefox (Not Installed)'.
    """
    browser_type = browser_type.lower().strip()
    if browser_type not in SUPPORTED_BROWSERS:
        return browser_type
    installed = find_browser_binary(browser_type) is not None
    display = browser_type.capitalize()
    return f"{display} (Installed)" if installed else f"{display} (Not Installed)"


def detect_default_browser() -> tuple[str, str | None]:
    """Auto-detect primary browser installed on system based on preference order.

    Returns:
        Tuple of (browser_type, binary_path_or_None).
        Defaults to ('chrome', None) if no browser can be detected.
    """
    for b_type in PREFERENCE_ORDER:
        binary = find_browser_binary(b_type)
        if binary:
            logger.info(f"Auto-detected browser '{b_type}' at: {binary}")
            return b_type, binary

    logger.warning("No supported browser detected; falling back to default 'chrome'")
    return "chrome", None
