"""Platform detection and PKCS#11 library path discovery."""

import os
import platform
from pathlib import Path
from dataclasses import dataclass


@dataclass
class PKCS11LibraryInfo:
    """Information about a PKCS#11 library."""
    path: Path
    name: str
    exists: bool


# Known PKCS#11 library paths for LuxTrust middleware
LUXTRUST_PATHS = {
    "Windows": [
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
        / "LuxTrust"
        / "LuxTrust Middleware"
        / "lux_p11.dll",
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "LuxTrust"
        / "LuxTrust Middleware"
        / "lux_p11.dll",
    ],
    "Linux": [
        # Gemalto middleware (required for LuxTrust cards)
        Path("/usr/lib/pkcs11/libgclib.so"),
        Path("/usr/lib/ClassicClient/libgclib.so"),
        # LuxTrust middleware paths
        Path("/usr/lib/x86_64-linux-gnu/liblux_p11.so"),
        Path("/usr/lib/liblux_p11.so"),
        Path("/opt/LuxTrust/lib/liblux_p11.so"),
        Path("/usr/local/lib/liblux_p11.so"),
        # OpenSC PKCS#11 (fallback)
        Path("/usr/lib/x86_64-linux-gnu/opensc-pkcs11.so"),
        Path("/usr/lib/opensc-pkcs11.so"),
    ],
    "Darwin": [
        Path("/Library/LuxTrust/lib/liblux_p11.dylib"),
        Path("/usr/local/lib/liblux_p11.dylib"),
    ],
}


def get_current_os() -> str:
    """Get the current operating system name."""
    return platform.system()


def discover_pkcs11_library() -> Path | None:
    """
    Discover the PKCS#11 library for the current platform.

    Returns:
        Path to the library if found, None otherwise.
    """
    current_os = get_current_os()
    paths = LUXTRUST_PATHS.get(current_os, [])

    for path in paths:
        if path.exists():
            return path

    return None


def get_all_pkcs11_candidates() -> list[PKCS11LibraryInfo]:
    """
    Get all candidate PKCS#11 library paths for the current platform.

    Returns:
        List of PKCS11LibraryInfo with existence status.
    """
    current_os = get_current_os()
    paths = LUXTRUST_PATHS.get(current_os, [])

    return [
        PKCS11LibraryInfo(
            path=p,
            name=p.name,
            exists=p.exists()
        )
        for p in paths
    ]


def validate_pkcs11_library(path: Path) -> bool:
    """
    Validate that a path points to a valid PKCS#11 library.

    Args:
        path: Path to the library file.

    Returns:
        True if the file exists and has the correct extension.
    """
    if not path.exists():
        return False

    current_os = get_current_os()
    valid_extensions = {
        "Windows": ".dll",
        "Linux": ".so",
        "Darwin": ".dylib",
    }

    expected_ext = valid_extensions.get(current_os, "")
    return path.suffix == expected_ext or expected_ext in path.name
