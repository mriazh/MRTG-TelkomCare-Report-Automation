"""
Diagnostic test to solve TelkomCare captcha using the configured Gemini model.
"""

import time
import base64
import json
import urllib.request
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from mrtg_automation.config import Config
from mrtg_automation.shared.paths import ROOT_DIR, ensure_directories

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_gemini_ocr")


def solve_with_gemini(api_key: str, models: list[str], image_bytes: bytes) -> str:
    import re

    img_b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": "Solve this text CAPTCHA. It is a 3-character alphanumeric string (case-sensitive). Output ONLY the solved 3-character string, with no other characters, formatting, wrapper, explanation, or newlines."
                    },
                    {"inline_data": {"mime_type": "image/png", "data": img_b64}},
                ]
            }
        ]
    }

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        logger.info(f"Trying Gemini model {model}.")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                res_json = json.loads(response.read().decode("utf-8"))
                text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                if re.fullmatch(r"[A-Za-z0-9]{3}", text):
                    return text
                logger.warning(f"Model {model} returned invalid output: {text}")
        except Exception as e:
            logger.warning(f"Model {model} failed: {e}")
    return ""


def main():
    ensure_directories()
    config = Config()

    api_key = config.gemini_api_key
    models = config.gemini_models

    if not api_key:
        logger.error("No Gemini API key available. Set GEMINI_API_KEY in config/.env")
        return

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")

    logger.info("Opening headless Chrome to capture captcha.")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)

    try:
        url = "https://telkomcare.telkom.co.id/public/login?modules=mrtgnetcare2"
        driver.get(url)
        time.sleep(3)

        # Locate and screenshot captcha image
        img_el = driver.find_element(By.CSS_SELECTOR, "#captcha-element img")
        png_bytes = img_el.screenshot_as_png

        # Save captcha image to disk so user can manually cross-check
        save_path = ROOT_DIR / "output" / "captcha_test.png"
        open(save_path, "wb").write(png_bytes)
        logger.info(f"Target captcha image saved to: {save_path}")

        # Solve it via Gemini API
        Solved_text = solve_with_gemini(api_key, models, png_bytes)
        logger.info("=" * 60)
        if Solved_text:
            logger.info(f"[SUCCESS] Gemini Captcha Output: '{Solved_text}'")
        else:
            logger.warning("[FAIL] All Gemini models returned no solution.")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error executing test: {e}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
