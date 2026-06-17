import os
from dotenv import load_dotenv
from .shared.paths import CONFIG_DIR

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
