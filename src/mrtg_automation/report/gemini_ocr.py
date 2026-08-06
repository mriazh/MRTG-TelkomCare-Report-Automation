"""Gemini Vision API for MRTG legend extraction."""

import base64
import json
import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from mrtg_automation.config import Config

logger = logging.getLogger(__name__)

MRTG_LEGEND_PROMPT = """Analyze this MRTG network traffic graph image. Extract ONLY the legend values from the bottom of the image.

Return the values in this EXACT format (no additional text):
Inbound_Current: [value]
Inbound_Average: [value]
Inbound_Maximum: [value]
Outbound_Current: [value]
Outbound_Average: [value]
Outbound_Maximum: [value]

Values should include units (e.g., "6.65 k", "1.82 M", "N/A").

If a value is not visible or unclear, write "N/A" for that line."""


class GeminiLegendExtractor:
    """Gemini Vision API for MRTG legend extraction."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.api_key = config.gemini_api_key
        self.models = config.gemini_models
        self.timeout = 30

    def extract_legend(self, image_path: Path) -> dict[str, Any]:
        """Extract MRTG legend values using Gemini Vision API."""
        if not self.api_key:
            return {"values": {}, "model": "", "complete": False, "error_reason": "API_KEY_MISSING"}

        image_bytes = image_path.read_bytes()
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": MRTG_LEGEND_PROMPT},
                        {"inline_data": {"mime_type": "image/png", "data": image_b64}},
                    ]
                }
            ]
        }

        attempted_models = []
        model_failures = {}
        attempts = 0

        for model in self.models:
            attempted_models.append(model)
            model_failures[model] = 0
            logger.info("[OCR] Gemini model=%s status=attempt", model)

            while model_failures[model] < 3:
                attempts += 1
                result_text, error_reason = self._try_model(model, payload)

                if result_text:
                    values = self._parse_legend_response(result_text)
                    if self._is_complete(values):
                        logger.info("[OCR] Gemini model=%s status=success", model)
                        return {
                            "values": values,
                            "model": model,
                            "complete": True,
                            "error_reason": None,
                            "attempted_models": attempted_models,
                            "model_failures": model_failures,
                            "attempts": attempts,
                        }
                    error_reason = "INCOMPLETE_RESPONSE"

                model_failures[model] += 1
                logger.info("[OCR] Gemini model=%s status=%s", model, error_reason)

        return {
            "values": {},
            "model": "",
            "complete": False,
            "error_reason": "ALL_MODELS_FAILED",
            "attempted_models": attempted_models,
            "model_failures": model_failures,
            "attempts": attempts,
        }

    def _try_model(self, model: str, payload: dict) -> tuple[str, str]:
        """Try a single Gemini model with retries for transient errors."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                text = self._extract_text_from_response(res_data)
                if text:
                    return text, ""
                return "", "INVALID_FORMAT"
        except urllib.error.HTTPError as e:
            logger.info("[OCR] Gemini model=%s status=http_%d", model, e.code)
            return "", f"HTTP_{e.code}"
        except (urllib.error.URLError, TimeoutError):
            logger.info("[OCR] Gemini model=%s status=timeout", model)
            return "", "TIMEOUT"
        except (ValueError, KeyError, IndexError, TypeError):
            logger.info("[OCR] Gemini model=%s status=invalid_response", model)
            return "", "INVALID_FORMAT"
        except (OSError, RuntimeError):
            logger.info("[OCR] Gemini model=%s status=error", model)
            return "", "FAILED"

    def _extract_text_from_response(self, data: dict) -> str:
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                return ""
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                return ""
            return parts[0].get("text", "").strip()
        except (KeyError, IndexError):
            return ""

    def _parse_legend_response(self, text: str) -> dict[str, str]:
        result = {}
        lines = text.strip().split("\n")

        expected_keys = [
            "Inbound_Current",
            "Inbound_Average",
            "Inbound_Maximum",
            "Outbound_Current",
            "Outbound_Average",
            "Outbound_Maximum",
        ]

        for line in lines:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key in expected_keys:
                result[key] = value

        # Fill missing with N/A to simplify completeness check
        for k in expected_keys:
            if k not in result:
                result[k] = "N/A"
        return result

    def _is_complete(self, values: dict[str, str]) -> bool:
        for v in values.values():
            if not v or v.lower() == "n/a":
                return False
        return True
