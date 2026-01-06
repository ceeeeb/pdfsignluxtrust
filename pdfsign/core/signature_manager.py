"""PDF signature manager using pyHanko."""

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from datetime import datetime
from io import BytesIO

from PIL import Image

from pdfsign.utils.coordinates import PDFRect


class SignatureAppearanceType(Enum):
    """Type of signature appearance."""
    TEXT = auto()
    IMAGE = auto()
    TEXT_AND_IMAGE = auto()


class PAdESLevel(Enum):
    """PAdES signature conformance level."""
    B_B = "B-B"      # Basic
    B_T = "B-T"      # With timestamp
    B_LT = "B-LT"    # Long-term validation
    B_LTA = "B-LTA"  # Long-term archival


@dataclass
class SignatureAppearance:
    """Configuration for signature visual appearance."""
    type: SignatureAppearanceType = SignatureAppearanceType.TEXT

    # Text options
    name: str = ""
    reason: str = ""
    location: str = ""
    contact: str = ""
    include_date: bool = True
    font_size: int = 10

    # Image options
    image_path: Path | None = None
    image_data: bytes | None = None


@dataclass
class SignatureConfig:
    """Complete signature configuration."""
    position: PDFRect
    page: int = 0
    field_name: str = "Signature1"
    appearance: SignatureAppearance = field(default_factory=SignatureAppearance)
    pades_level: PAdESLevel = PAdESLevel.B_B


class SignatureManager:
    """
    Manager for creating PDF signatures with pyHanko.

    Handles:
    - Visual signature appearance (text or image)
    - Signature field creation
    - PAdES signing with PKCS#11
    """

    def __init__(self):
        self._last_error: str | None = None

    @property
    def last_error(self) -> str | None:
        """Get the last error message."""
        return self._last_error

    def create_stamp_style(
        self,
        appearance: SignatureAppearance
    ):
        """
        Create a pyHanko stamp style from appearance config.

        Args:
            appearance: Signature appearance configuration.

        Returns:
            StampStyle instance for pyHanko.
        """
        from pyhanko.sign.fields import VisibleSigSettings
        from pyhanko.stamp import TextStampStyle, QRStampStyle

        if appearance.type == SignatureAppearanceType.IMAGE and appearance.image_path:
            # Image-based signature
            return self._create_image_stamp(appearance)
        else:
            # Text-based signature
            return self._create_text_stamp(appearance)

    def _create_text_stamp(self, appearance: SignatureAppearance):
        """Create a text-based stamp style."""
        from pyhanko.stamp import TextStampStyle

        # Build text template
        lines = []
        if appearance.name:
            lines.append(f"Signe par: %(signer)s")
        if appearance.include_date:
            lines.append(f"Date: %(ts)s")
        if appearance.reason:
            lines.append(f"Raison: {appearance.reason}")
        if appearance.location:
            lines.append(f"Lieu: {appearance.location}")

        stamp_text = "\n".join(lines) if lines else "Signature electronique"

        return TextStampStyle(
            stamp_text=stamp_text,
            text_box_style=None,  # Use default
        )

    def _create_image_stamp(self, appearance: SignatureAppearance):
        """Create an image-based stamp style."""
        from pyhanko.stamp import TextStampStyle

        # For image stamps, we'll use the image as background
        # pyHanko supports this via the background parameter

        # Load and validate image
        if appearance.image_path and appearance.image_path.exists():
            image_path = str(appearance.image_path)
        elif appearance.image_data:
            # Save temporary image
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(appearance.image_data)
                image_path = f.name
        else:
            # Fallback to text
            return self._create_text_stamp(appearance)

        return TextStampStyle(
            stamp_text="%(signer)s\n%(ts)s",
            background=image_path,
        )

    def sign_pdf(
        self,
        input_path: Path | str,
        output_path: Path | str,
        signer,
        config: SignatureConfig,
    ) -> Path:
        """
        Sign a PDF document.

        Args:
            input_path: Path to input PDF.
            output_path: Path for signed PDF.
            signer: pyHanko signer (e.g., PKCS11Signer).
            config: Signature configuration.

        Returns:
            Path to the signed PDF.

        Raises:
            RuntimeError: If signing fails.
        """
        from pyhanko.sign import signers, fields
        from pyhanko.sign.fields import SigFieldSpec
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

        input_path = Path(input_path)
        output_path = Path(output_path)

        try:
            # Read input PDF
            with open(input_path, "rb") as f:
                reader = PdfFileReader(f)
                writer = IncrementalPdfFileWriter(f)

                # Create signature field spec
                sig_field_spec = SigFieldSpec(
                    sig_field_name=config.field_name,
                    on_page=config.page,
                    box=config.position.as_tuple(),
                )

                # Create stamp style
                stamp_style = self.create_stamp_style(config.appearance)

                # Configure signature metadata
                signature_meta = signers.PdfSignatureMetadata(
                    field_name=config.field_name,
                    reason=config.appearance.reason or None,
                    location=config.appearance.location or None,
                    contact_info=config.appearance.contact or None,
                    name=config.appearance.name or None,
                )

                # Create PDF signer
                pdf_signer = signers.PdfSigner(
                    signature_meta=signature_meta,
                    signer=signer,
                    stamp_style=stamp_style,
                    new_field_spec=sig_field_spec,
                )

                # Sign and write output
                with open(output_path, "wb") as out_f:
                    pdf_signer.sign_pdf(
                        writer,
                        output=out_f,
                    )

            return output_path

        except Exception as e:
            self._last_error = str(e)
            raise RuntimeError(f"Signing failed: {e}") from e

    def sign_pdf_simple(
        self,
        input_path: Path | str,
        output_path: Path | str,
        signer,
        position: PDFRect,
        page: int = 0,
        name: str = "",
        reason: str = "",
        location: str = "",
    ) -> Path:
        """
        Simplified signing with minimal configuration.

        Args:
            input_path: Path to input PDF.
            output_path: Path for signed PDF.
            signer: pyHanko signer.
            position: Signature position in PDF coordinates.
            page: Page number (0-indexed).
            name: Signer name.
            reason: Signing reason.
            location: Signing location.

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
            position=position,
            page=page,
            appearance=appearance,
        )

        return self.sign_pdf(input_path, output_path, signer, config)

    def validate_signature(self, pdf_path: Path | str) -> dict:
        """
        Validate signatures in a PDF.

        Args:
            pdf_path: Path to PDF to validate.

        Returns:
            Dictionary with validation results.
        """
        from pyhanko.sign.validation import validate_pdf_signature
        from pyhanko.pdf_utils.reader import PdfFileReader

        pdf_path = Path(pdf_path)
        results = {
            "valid": True,
            "signatures": [],
            "errors": [],
        }

        try:
            with open(pdf_path, "rb") as f:
                reader = PdfFileReader(f)

                for sig in reader.embedded_signatures:
                    try:
                        status = validate_pdf_signature(sig)
                        results["signatures"].append({
                            "field_name": sig.field_name,
                            "valid": status.bottom_line,
                            "signer": str(status.signing_cert.subject) if status.signing_cert else "Unknown",
                            "timestamp": status.timestamp_validity.timestamp if status.timestamp_validity else None,
                        })
                        if not status.bottom_line:
                            results["valid"] = False
                    except Exception as e:
                        results["signatures"].append({
                            "field_name": sig.field_name,
                            "valid": False,
                            "error": str(e),
                        })
                        results["valid"] = False

        except Exception as e:
            results["valid"] = False
            results["errors"].append(str(e))

        return results

    @staticmethod
    def generate_unique_field_name(pdf_path: Path | str) -> str:
        """
        Generate a unique signature field name.

        Args:
            pdf_path: Path to PDF to check for existing fields.

        Returns:
            Unique field name like "Signature1", "Signature2", etc.
        """
        from pyhanko.pdf_utils.reader import PdfFileReader

        existing_names = set()

        try:
            with open(pdf_path, "rb") as f:
                reader = PdfFileReader(f)
                for sig in reader.embedded_signatures:
                    existing_names.add(sig.field_name)
        except Exception:
            pass

        counter = 1
        while True:
            name = f"Signature{counter}"
            if name not in existing_names:
                return name
            counter += 1
