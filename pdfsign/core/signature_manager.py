"""PDF signature manager using Java/Gemalto backend."""

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from pdfsign.crypto.java_signer import JavaSigner, JavaSignerError, CertificateInfo


class SignatureAppearanceType(Enum):
    """Type of signature appearance."""
    TEXT = auto()
    IMAGE = auto()
    TEXT_AND_IMAGE = auto()


@dataclass
class SignatureAppearance:
    """Configuration for signature visual appearance."""
    type: SignatureAppearanceType = SignatureAppearanceType.TEXT
    name: str = ""
    reason: str = ""
    location: str = ""
    contact: str = ""
    include_date: bool = True
    font_size: int = 10
    image_path: Optional[Path] = None


@dataclass
class SignaturePosition:
    """Position and size of visible signature."""
    page: int = 1
    x: float = 50
    y: float = 50
    width: float = 200
    height: float = 50


@dataclass
class SignatureConfig:
    """Complete signature configuration."""
    position: SignaturePosition = field(default_factory=SignaturePosition)
    appearance: SignatureAppearance = field(default_factory=SignatureAppearance)
    visible: bool = True
    field_name: str = "Signature1"


class SignatureManager:
    """
    Manager for creating PDF signatures using Java/Gemalto backend.

    This replaces pyHanko with a Java-based solution that uses
    the Gemalto PKCS#11 middleware for LuxTrust smart cards.
    """

    def __init__(self, pkcs11_lib: Optional[str] = None):
        """
        Initialize the signature manager.

        Args:
            pkcs11_lib: Path to PKCS#11 library (auto-detected if None).
        """
        self._java_signer: Optional[JavaSigner] = None
        self._pkcs11_lib = pkcs11_lib
        self._last_error: Optional[str] = None

    @property
    def last_error(self) -> Optional[str]:
        """Get the last error message."""
        return self._last_error

    def _get_signer(self) -> JavaSigner:
        """Get or create the Java signer instance."""
        if self._java_signer is None:
            try:
                self._java_signer = JavaSigner(pkcs11_lib=self._pkcs11_lib)
            except JavaSignerError as e:
                self._last_error = str(e)
                raise
        return self._java_signer

    def list_certificates(self, pin: str, slot: int = 0) -> list[CertificateInfo]:
        """
        List certificates on the token.

        Args:
            pin: User PIN for the token.
            slot: PKCS#11 slot number.

        Returns:
            List of CertificateInfo objects.

        Raises:
            JavaSignerError: If certificates cannot be read.
        """
        try:
            signer = self._get_signer()
            return signer.list_certificates(pin, slot)
        except JavaSignerError as e:
            self._last_error = str(e)
            raise

    def sign_pdf(
        self,
        input_path: Path,
        output_path: Path,
        pin: str,
        config: Optional[SignatureConfig] = None,
        alias: Optional[str] = None,
        slot: int = 0,
    ) -> Path:
        """
        Sign a PDF document.

        Args:
            input_path: Path to input PDF.
            output_path: Path for signed PDF.
            pin: User PIN.
            config: Signature configuration.
            alias: Certificate alias (auto-detected if None).
            slot: PKCS#11 slot number.

        Returns:
            Path to the signed PDF.

        Raises:
            RuntimeError: If signing fails.
        """
        if config is None:
            config = SignatureConfig()

        try:
            signer = self._get_signer()

            result = signer.sign_pdf(
                input_path=Path(input_path),
                output_path=Path(output_path),
                pin=pin,
                alias=alias,
                slot=slot,
                reason=config.appearance.reason,
                location=config.appearance.location,
                contact=config.appearance.contact,
                name=config.appearance.name,
                image_path=str(config.appearance.image_path) if config.appearance.image_path else None,
                visible=config.visible,
                page=config.position.page,
                x=config.position.x,
                y=config.position.y,
                width=config.position.width,
                height=config.position.height,
            )

            if not result.success:
                self._last_error = result.error or "Signing failed"
                raise RuntimeError(self._last_error)

            return Path(output_path)

        except JavaSignerError as e:
            self._last_error = str(e)
            raise RuntimeError(f"Signing failed: {e}") from e

    def sign_pdf_simple(
        self,
        input_path: Path,
        output_path: Path,
        pin: str,
        position: Optional[SignaturePosition] = None,
        name: str = "",
        reason: str = "",
        location: str = "",
        alias: Optional[str] = None,
        slot: int = 0,
    ) -> Path:
        """
        Simplified signing with minimal configuration.

        Args:
            input_path: Path to input PDF.
            output_path: Path for signed PDF.
            pin: User PIN.
            position: Signature position.
            name: Signer name.
            reason: Signing reason.
            location: Signing location.
            alias: Certificate alias.
            slot: PKCS#11 slot number.

        Returns:
            Path to the signed PDF.
        """
        appearance = SignatureAppearance(
            type=SignatureAppearanceType.TEXT,
            name=name,
            reason=reason,
            location=location,
            include_date=True,
        )

        config = SignatureConfig(
            position=position or SignaturePosition(),
            appearance=appearance,
            visible=True,
        )

        return self.sign_pdf(input_path, output_path, pin, config, alias, slot)

    def test_connection(self, pin: str, slot: int = 0) -> bool:
        """
        Test if the token is accessible.

        Args:
            pin: User PIN.
            slot: PKCS#11 slot number.

        Returns:
            True if connection successful.
        """
        try:
            signer = self._get_signer()
            return signer.test_connection(pin, slot)
        except JavaSignerError:
            return False

    @staticmethod
    def generate_unique_field_name(pdf_path: Path) -> str:
        """
        Generate a unique signature field name.

        Args:
            pdf_path: Path to PDF to check for existing fields.

        Returns:
            Unique field name like "Signature1", "Signature2", etc.
        """
        # Simple implementation - could be enhanced to check existing fields
        import time
        return f"Signature_{int(time.time())}"
