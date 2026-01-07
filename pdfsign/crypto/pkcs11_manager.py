"""PKCS#11 token management using Java backend."""

from dataclasses import dataclass
from pathlib import Path

from pdfsign.utils.platform import discover_pkcs11_library, validate_pkcs11_library
from pdfsign.crypto.java_signer import JavaSigner, JavaSignerError, CertificateInfo as JavaCertInfo


@dataclass
class TokenInfo:
    """Information about a PKCS#11 token."""
    slot_id: int
    label: str
    manufacturer: str
    model: str
    serial: str


@dataclass
class CertificateInfo:
    """Information about a certificate on the token."""
    label: str
    subject_cn: str
    issuer_cn: str
    serial_number: str
    not_before: str
    not_after: str
    key_id: bytes
    can_sign: bool


class PKCS11Error(Exception):
    """Exception for PKCS#11 related errors."""
    pass


class PKCS11Manager:
    """
    Manager for PKCS#11 token operations.

    Uses Java backend with Gemalto PKCS#11 for LuxTrust cards.
    """

    def __init__(self, lib_path: Path | str | None = None):
        """
        Initialize the PKCS#11 manager.

        Args:
            lib_path: Path to PKCS#11 library. Auto-detected if None.

        Raises:
            PKCS11Error: If library cannot be found or loaded.
        """
        self._lib_path: Path | None = None
        self._java_signer: JavaSigner | None = None

        if lib_path:
            path = Path(lib_path)
            if not validate_pkcs11_library(path):
                raise PKCS11Error(f"Invalid PKCS#11 library: {path}")
            self._lib_path = path
        else:
            self._lib_path = discover_pkcs11_library()
            if not self._lib_path:
                raise PKCS11Error(
                    "PKCS#11 library not found. "
                    "Please install Gemalto Middleware or specify library path."
                )

        # Initialize Java signer
        try:
            self._java_signer = JavaSigner(pkcs11_lib=str(self._lib_path))
        except JavaSignerError as e:
            raise PKCS11Error(f"Failed to initialize Java signer: {e}")

    @property
    def library_path(self) -> Path | None:
        """Get the PKCS#11 library path."""
        return self._lib_path

    @property
    def is_session_open(self) -> bool:
        """Check if a session is currently open."""
        return self._java_signer is not None

    def list_tokens(self) -> list[TokenInfo]:
        """
        List all available PKCS#11 tokens.

        Returns:
            List of TokenInfo for each detected token.

        Raises:
            PKCS11Error: If tokens cannot be enumerated.
        """
        # Return a default token for slot 0 (LuxTrust cards use slot 0)
        # The Java signer will verify if the token is present when listing certs
        return [TokenInfo(
            slot_id=0,
            label="LuxTrust",
            manufacturer="Thales DIS",
            model="Smart Card",
            serial="",
        )]

    def list_certificates(self, slot_id: int, pin: str) -> list[CertificateInfo]:
        """
        List certificates on a specific token.

        Args:
            slot_id: PKCS#11 slot ID.
            pin: User PIN for the token.

        Returns:
            List of CertificateInfo for signing certificates.

        Raises:
            PKCS11Error: If certificates cannot be read.
        """
        if not self._java_signer:
            raise PKCS11Error("Java signer not initialized")

        try:
            java_certs = self._java_signer.list_certificates(pin, slot_id)
            certs = []

            for jc in java_certs:
                # Extract CN from subject
                subject_cn = self._extract_cn(jc.subject)

                certs.append(CertificateInfo(
                    label=jc.alias,
                    subject_cn=subject_cn,
                    issuer_cn=self._extract_cn(jc.issuer),
                    serial_number=jc.serial,
                    not_before=jc.not_before,
                    not_after=jc.not_after,
                    key_id=jc.alias.encode(),
                    can_sign=jc.can_sign,
                ))

            # Filter to only signing certificates
            return [c for c in certs if c.can_sign]

        except JavaSignerError as e:
            error_msg = str(e).lower()
            if "pin" in error_msg:
                raise PKCS11Error("Invalid PIN") from e
            raise PKCS11Error(f"Failed to list certificates: {e}") from e

    def _extract_cn(self, dn: str) -> str:
        """Extract Common Name from distinguished name string."""
        # DN format: CN=Name,OU=...,O=...,C=...
        for part in dn.split(","):
            part = part.strip()
            if part.upper().startswith("CN="):
                return part[3:]
        return dn

    def get_java_signer(self) -> JavaSigner:
        """Get the underlying Java signer instance."""
        if not self._java_signer:
            raise PKCS11Error("Java signer not initialized")
        return self._java_signer

    def test_pin(self, slot_id: int, pin: str) -> bool:
        """
        Test if a PIN is valid for a token.

        Args:
            slot_id: PKCS#11 slot ID.
            pin: PIN to test.

        Returns:
            True if PIN is valid, False otherwise.
        """
        if not self._java_signer:
            return False

        try:
            return self._java_signer.test_connection(pin, slot_id)
        except JavaSignerError:
            return False
