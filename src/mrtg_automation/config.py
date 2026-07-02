import os
import logging
from dotenv import load_dotenv
from .shared.paths import CONFIG_DIR

logger = logging.getLogger('mrtg_automation.config')

class Config:
    def __init__(self):
        # Load environment variables from config/.env
        env_path = CONFIG_DIR / ".env"
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
        self.browser_type = os.getenv("BROWSER_TYPE", "chrome").lower()
        if self.browser_type not in ["chrome", "chromium", "firefox", "edge"]:
            logger.warning(f"Invalid BROWSER_TYPE '{self.browser_type}', defaulting to 'chrome'")
            self.browser_type = "chrome"
        self.browser_binary = os.getenv("BROWSER_BINARY_LOCATION")
        # Auto-login credentials (optional)
        self.auto_login_enabled = os.getenv("AUTO_LOGIN_ENABLED", "false").lower() in ("true", "1", "yes")
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
                self.gemini_models = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3-flash-preview"]
