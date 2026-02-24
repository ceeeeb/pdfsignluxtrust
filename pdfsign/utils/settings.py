"""Settings persistence for PDF Signer application."""

import json
import logging
from pathlib import Path

from pdfsign.core.signature_manager import SignatureAppearance, SignatureAppearanceType

logger = logging.getLogger(__name__)

CONFIG_DIR_NAME = "pdfsign-luxtrust"
SETTINGS_FILENAME = "settings.json"


def get_config_dir() -> Path:
    """Get the configuration directory."""
    config_dir = Path.home() / ".config" / CONFIG_DIR_NAME
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_settings_file() -> Path:
    """Get the settings file path."""
    return get_config_dir() / SETTINGS_FILENAME


def _load_settings() -> dict:
    """Load all settings from the settings file."""
    settings_file = get_settings_file()
    if not settings_file.exists():
        return {}
    try:
        with open(settings_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning("Failed to load settings: %s", e)
        return {}


def _save_settings(data: dict) -> None:
    """Merge data into existing settings and save."""
    existing = _load_settings()
    existing.update(data)

    settings_file = get_settings_file()
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


def save_signature_appearance(appearance: SignatureAppearance) -> None:
    """Save signature appearance settings to file."""
    _save_settings({
        "signature_appearance": {
            "type": appearance.type.value,
            "name": appearance.name,
            "reason": appearance.reason,
            "location": appearance.location,
            "contact": appearance.contact,
            "include_date": appearance.include_date,
            "font_size": appearance.font_size,
            "image_path": str(appearance.image_path) if appearance.image_path else None,
        }
    })


def load_signature_appearance() -> SignatureAppearance | None:
    """Load signature appearance settings from file."""
    settings = _load_settings()
    sig_data = settings.get("signature_appearance")
    if not sig_data:
        return None

    try:
        sig_type = SignatureAppearanceType(
            sig_data.get("type", SignatureAppearanceType.TEXT.value)
        )
    except ValueError:
        sig_type = SignatureAppearanceType.TEXT

    image_path = sig_data.get("image_path")
    if image_path:
        image_path = Path(image_path)
        if not image_path.exists():
            image_path = None

    return SignatureAppearance(
        type=sig_type,
        name=sig_data.get("name", ""),
        reason=sig_data.get("reason", ""),
        location=sig_data.get("location", ""),
        contact=sig_data.get("contact", ""),
        include_date=sig_data.get("include_date", True),
        font_size=sig_data.get("font_size", 10),
        image_path=image_path,
    )


def save_pkcs11_library(lib_path: str) -> None:
    """Save the PKCS#11 library path."""
    _save_settings({"pkcs11_library": lib_path})


def load_pkcs11_library() -> str | None:
    """Load the saved PKCS#11 library path."""
    return _load_settings().get("pkcs11_library")
