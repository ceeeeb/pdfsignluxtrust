"""Settings persistence for PDF Signer application."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from pdfsign.core.signature_manager import SignatureAppearance, SignatureAppearanceType


def get_config_dir() -> Path:
    """Get the configuration directory."""
    config_dir = Path.home() / ".config" / "pdfsign-luxtrust"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_settings_file() -> Path:
    """Get the settings file path."""
    return get_config_dir() / "settings.json"


def save_signature_appearance(appearance: SignatureAppearance) -> None:
    """
    Save signature appearance settings to file.

    Args:
        appearance: SignatureAppearance to save.
    """
    settings_file = get_settings_file()

    # Convert to dict
    data = {
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
    }

    # Load existing settings and merge
    existing = {}
    if settings_file.exists():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    existing.update(data)

    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


def load_signature_appearance() -> Optional[SignatureAppearance]:
    """
    Load signature appearance settings from file.

    Returns:
        SignatureAppearance if settings exist, None otherwise.
    """
    settings_file = get_settings_file()

    if not settings_file.exists():
        return None

    try:
        with open(settings_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        sig_data = data.get("signature_appearance")
        if not sig_data:
            return None

        # Convert type enum
        type_value = sig_data.get("type", SignatureAppearanceType.TEXT.value)
        try:
            sig_type = SignatureAppearanceType(type_value)
        except ValueError:
            sig_type = SignatureAppearanceType.TEXT

        # Convert image path
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

    except (json.JSONDecodeError, IOError, KeyError):
        return None


def save_pkcs11_library(lib_path: str) -> None:
    """Save the PKCS#11 library path."""
    settings_file = get_settings_file()

    existing = {}
    if settings_file.exists():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    existing["pkcs11_library"] = lib_path

    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


def load_pkcs11_library() -> Optional[str]:
    """Load the saved PKCS#11 library path."""
    settings_file = get_settings_file()

    if not settings_file.exists():
        return None

    try:
        with open(settings_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("pkcs11_library")
    except (json.JSONDecodeError, IOError):
        return None
