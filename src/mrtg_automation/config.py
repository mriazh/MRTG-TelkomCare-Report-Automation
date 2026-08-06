import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from .shared.browser_detection import detect_default_browser, find_browser_binary
from .shared.config_models import ApplicationSettings
from .shared.paths import CONFIG_DIR

logger = logging.getLogger("mrtg_automation.config")

GEMINI_MODELS_DEFAULT = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3-flash",
]


class Config:
    def __init__(self, config_dir=None):
        config_root = (
            Path(config_dir).expanduser().resolve() if config_dir is not None else CONFIG_DIR
        )
        # Load environment variables from config/.env
        env_path = config_root / ".env"
        load_dotenv(dotenv_path=env_path)

        # Base URLs for each mode
        self.BASE_URL_SID = os.getenv("BASE_URL_SID", "")
        self.BASE_URL_GRAPH = os.getenv("BASE_URL_GRAPH", "")

        # Scraper constants & retries
        self.WAIT_TIMEOUT = int(os.getenv("WAIT_TIMEOUT", 10))
        self.LONG_TIMEOUT = int(os.getenv("LONG_TIMEOUT", 30))
        self.LOGIN_WAIT = int(os.getenv("LOGIN_WAIT", 60))
        self.MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
        self.MAX_GRAPH_RETRIES = int(os.getenv("MAX_GRAPH_RETRIES", 2))

        # Browser configuration
        self.browser_type = os.getenv("BROWSER_TYPE", "auto").lower()
        if self.browser_type not in ["auto", "chrome", "chromium", "firefox", "edge"]:
            logger.warning(f"Invalid BROWSER_TYPE '{self.browser_type}', defaulting to 'auto'")
            self.browser_type = "auto"
        self.effective_browser_type = "chrome"
        self.browser_binary = os.getenv("BROWSER_BINARY_LOCATION")
        self.resolve_browser()

    def resolve_browser(self):
        """Resolve effective browser type and binary location."""
        if self.browser_type == "auto":
            detected_type, detected_binary = detect_default_browser()
            self.effective_browser_type = detected_type
            if not self.browser_binary and detected_binary:
                self.browser_binary = detected_binary
        else:
            self.effective_browser_type = self.browser_type
            if not self.browser_binary:
                self.browser_binary = find_browser_binary(self.browser_type)

        # Auto-login credentials (optional)
        self.auto_login_enabled = os.getenv("AUTO_LOGIN_ENABLED", "false").lower() in (
            "true",
            "1",
            "yes",
        )
        self.telkom_user = os.getenv("TELKOM_USER", "")
        self.telkom_password = os.getenv("TELKOM_PASSWORD", "")
        self.totp_secret = os.getenv("TOTP_SECRET", "")

        # Gemini CAPTCHA solving
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
        models_env = os.getenv("GEMINI_MODELS", "").strip()
        if models_env:
            self.gemini_models = [m.strip() for m in models_env.split(",") if m.strip()]
        else:
            legacy_model = os.getenv("GEMINI_MODEL", "").strip()
            if legacy_model:
                self.gemini_models = [legacy_model]
            else:
                self.gemini_models = list(GEMINI_MODELS_DEFAULT)

        # OCR Settings
        try:
            threshold = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.85"))
            if 0.0 <= threshold <= 1.0:
                self.ocr_confidence_threshold = threshold
            else:
                self.ocr_confidence_threshold = 0.85
        except (ValueError, TypeError):
            self.ocr_confidence_threshold = 0.85
        self.ocr_gemini_observe = os.getenv("OCR_GEMINI_OBSERVE", "false").lower() in (
            "true",
            "1",
            "yes",
        )
        try:
            self.ocr_max_retries = max(1, min(10, int(os.getenv("OCR_MAX_RETRIES", "3"))))
        except (ValueError, TypeError):
            self.ocr_max_retries = 3

        # Validate the completed environment at the boundary while retaining
        # this legacy facade for existing scraper/report consumers. Invalid
        # local input falls back to the safe defaults above and is never logged.
        try:
            self.settings = ApplicationSettings.from_legacy_config(self)
        except Exception as exc:
            logger.warning("Configuration validation failed: %s", type(exc).__name__)
            self.settings = None
