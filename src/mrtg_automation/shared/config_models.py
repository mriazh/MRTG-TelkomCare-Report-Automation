"""Validated configuration and target-list boundary models.

The application still exposes its historical ``Config`` and tuple target
interfaces to the scraper/reporting code.  These models validate data at the
input boundary without changing those downstream contracts.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator


class BrowserType(StrEnum):
    AUTO = "auto"
    CHROME = "chrome"
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    EDGE = "edge"


class ApplicationSettings(BaseModel):
    """Safe, bounded settings model for values loaded from ``config/.env``."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    base_url_sid: str = ""
    base_url_graph: str = ""
    wait_timeout: int = Field(default=10, ge=1, le=600)
    long_timeout: int = Field(default=30, ge=1, le=3600)
    login_wait: int = Field(default=60, ge=1, le=3600)
    max_retries: int = Field(default=3, ge=1, le=10)
    max_graph_retries: int = Field(default=2, ge=1, le=10)
    browser_type: BrowserType = BrowserType.AUTO
    browser_binary_location: str | None = None
    auto_login_enabled: bool = False
    telkom_user: str = ""
    telkom_password: SecretStr = Field(default_factory=lambda: SecretStr(""))
    totp_secret: SecretStr = Field(default_factory=lambda: SecretStr(""))
    gemini_api_key: SecretStr = Field(default_factory=lambda: SecretStr(""))
    gemini_models: list[str] = Field(default_factory=list, min_length=1)
    ocr_confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    ocr_gemini_observe: bool = False
    ocr_max_retries: int = Field(default=3, ge=1, le=10)

    @field_validator("gemini_models")
    @classmethod
    def validate_models(cls, models: list[str]) -> list[str]:
        cleaned = [model.strip() for model in models if model.strip()]
        if not cleaned:
            raise ValueError("at least one Gemini model is required")
        return cleaned

    @classmethod
    def from_legacy_config(cls, config: Any) -> "ApplicationSettings":
        """Build a safe model from the existing ``Config`` facade."""

        return cls(
            base_url_sid=getattr(config, "BASE_URL_SID", ""),
            base_url_graph=getattr(config, "BASE_URL_GRAPH", ""),
            wait_timeout=getattr(config, "WAIT_TIMEOUT", 10),
            long_timeout=getattr(config, "LONG_TIMEOUT", 30),
            login_wait=getattr(config, "LOGIN_WAIT", 60),
            max_retries=getattr(config, "MAX_RETRIES", 3),
            max_graph_retries=getattr(config, "MAX_GRAPH_RETRIES", 2),
            browser_type=BrowserType(getattr(config, "browser_type", "auto")),
            browser_binary_location=getattr(config, "browser_binary", None),
            auto_login_enabled=getattr(config, "auto_login_enabled", False),
            telkom_user=getattr(config, "telkom_user", ""),
            telkom_password=SecretStr(getattr(config, "telkom_password", "")),
            totp_secret=SecretStr(getattr(config, "totp_secret", "")),
            gemini_api_key=SecretStr(getattr(config, "gemini_api_key", "")),
            gemini_models=list(getattr(config, "gemini_models", [])),
            ocr_confidence_threshold=getattr(config, "ocr_confidence_threshold", 0.85),
            ocr_gemini_observe=getattr(config, "ocr_gemini_observe", False),
            ocr_max_retries=getattr(config, "ocr_max_retries", 3),
        )

    def safe_errors(self, exc: ValidationError) -> list[dict[str, str]]:
        """Return field/status errors without including rejected input values."""

        return [
            {
                "field": ".".join(str(part) for part in error.get("loc", ())),
                "message": str(error.get("msg", "invalid value")),
                "type": str(error.get("type", "value_error")),
            }
            for error in exc.errors(include_url=False, include_context=False)
        ]


class TargetRow(BaseModel):
    """Validated representation of one CSV target-list row."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    type: str = Field(min_length=1, max_length=32)
    target: str = Field(min_length=1, max_length=256)
    ocr_enabled: bool = False
    image_enabled: bool = False

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"sid", "graph-title", "graphtitle"}:
            raise ValueError("type must be SID or Graph-title")
        return value

    @field_validator("target")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        if any(ord(char) < 32 for char in value):
            raise ValueError("target contains unsupported control characters")
        return value

    def as_legacy_tuple(self, display_index: int) -> tuple[str, str, str]:
        return str(display_index), self.type, self.target


def load_target_row(row: dict[str, Any]) -> TargetRow:
    """Validate a raw CSV mapping and return a safe typed target row."""

    return TargetRow.model_validate(row)


def validate_settings(config: Any) -> ApplicationSettings:
    """Validate a legacy config object at the compatibility boundary."""

    return ApplicationSettings.from_legacy_config(config)


__all__ = [
    "ApplicationSettings",
    "BrowserType",
    "TargetRow",
    "ValidationError",
    "load_target_row",
    "validate_settings",
]
