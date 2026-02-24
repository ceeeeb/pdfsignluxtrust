"""PDF document wrapper using PyMuPDF."""

import logging
from pathlib import Path
from dataclasses import dataclass

import pymupdf

logger = logging.getLogger(__name__)
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import QByteArray


@dataclass
class PageInfo:
    """Information about a PDF page."""
    number: int
    width: float
    height: float
    rotation: int


@dataclass
class SignatureInfo:
    """Information about an existing signature in the PDF."""
    field_name: str
    page: int
    signer: str
    signed_on: str
    is_valid: bool | None  # None if validation not possible


class PDFDocument:
    """Wrapper around PyMuPDF for PDF operations."""

    def __init__(self):
        self._doc: pymupdf.Document | None = None
        self._path: Path | None = None

    @property
    def is_open(self) -> bool:
        """Check if a document is currently open."""
        return self._doc is not None

    @property
    def path(self) -> Path | None:
        """Get the path of the currently open document."""
        return self._path

    @property
    def page_count(self) -> int:
        """Get the number of pages in the document."""
        if not self._doc:
            return 0
        return len(self._doc)

    def open(self, file_path: str | Path) -> None:
        """
        Open a PDF document.

        Args:
            file_path: Path to the PDF file.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            RuntimeError: If the file cannot be opened.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {path}")

        try:
            self._doc = pymupdf.open(str(path))
            self._path = path
        except Exception as e:
            raise RuntimeError(f"Failed to open PDF: {e}") from e

    def close(self) -> None:
        """Close the current document."""
        if self._doc:
            self._doc.close()
            self._doc = None
            self._path = None

    def get_page_info(self, page_num: int) -> PageInfo:
        """
        Get information about a specific page.

        Args:
            page_num: Page number (0-indexed).

        Returns:
            PageInfo with dimensions and rotation.

        Raises:
            ValueError: If page number is invalid.
        """
        if not self._doc:
            raise RuntimeError("No document is open")

        if page_num < 0 or page_num >= len(self._doc):
            raise ValueError(f"Invalid page number: {page_num}")

        page = self._doc[page_num]
        rect = page.rect

        return PageInfo(
            number=page_num,
            width=rect.width,
            height=rect.height,
            rotation=page.rotation
        )

    def render_page(
        self,
        page_num: int,
        zoom: float = 1.0,
        alpha: bool = False
    ) -> QPixmap:
        """
        Render a page to a QPixmap.

        Args:
            page_num: Page number (0-indexed).
            zoom: Zoom factor (1.0 = 72 DPI).
            alpha: Include alpha channel.

        Returns:
            QPixmap of the rendered page.

        Raises:
            RuntimeError: If no document is open.
            ValueError: If page number is invalid.
        """
        if not self._doc:
            raise RuntimeError("No document is open")

        if page_num < 0 or page_num >= len(self._doc):
            raise ValueError(f"Invalid page number: {page_num}")

        page = self._doc[page_num]

        # Create transformation matrix for zoom
        mat = pymupdf.Matrix(zoom, zoom)

        # Render page to pixmap
        pix = page.get_pixmap(matrix=mat, alpha=alpha)

        # Convert to QImage
        if pix.alpha:
            fmt = QImage.Format.Format_RGBA8888
        else:
            fmt = QImage.Format.Format_RGB888

        img = QImage(
            pix.samples,
            pix.width,
            pix.height,
            pix.stride,
            fmt
        )

        # Must copy because pix.samples is temporary
        return QPixmap.fromImage(img.copy())

    def render_page_to_bytes(
        self,
        page_num: int,
        zoom: float = 1.0,
        image_format: str = "png"
    ) -> bytes:
        """
        Render a page to bytes (PNG or JPEG).

        Args:
            page_num: Page number (0-indexed).
            zoom: Zoom factor.
            image_format: Output format ("png" or "jpeg").

        Returns:
            Image data as bytes.
        """
        if not self._doc:
            raise RuntimeError("No document is open")

        page = self._doc[page_num]
        mat = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        return pix.tobytes(image_format)

    def get_page_text(self, page_num: int) -> str:
        """
        Extract text from a page.

        Args:
            page_num: Page number (0-indexed).

        Returns:
            Text content of the page.
        """
        if not self._doc:
            raise RuntimeError("No document is open")

        page = self._doc[page_num]
        return page.get_text()

    def get_signatures(self) -> list[SignatureInfo]:
        """
        Get information about existing digital signatures in the document.

        Returns:
            List of SignatureInfo objects for each signature found.
        """
        if not self._doc:
            return []

        signatures = []

        for page_num in range(len(self._doc)):
            page = self._doc[page_num]

            # Get all widgets (form fields) on the page
            for widget in page.widgets():
                if widget.field_type == pymupdf.PDF_WIDGET_TYPE_SIGNATURE:
                    # Extract signature information
                    field_name = widget.field_name or "Unknown"
                    signer = ""
                    signed_on = ""

                    try:
                        sig_value = widget.field_value
                        if sig_value and isinstance(sig_value, dict):
                            signer = sig_value.get("Name", "")
                            signed_on = sig_value.get("M", "")
                    except Exception:
                        logger.debug("Could not read signature value for field %s", field_name)

                    if not signer:
                        try:
                            display = widget.field_display or ""
                            if display:
                                signer = display
                        except Exception:
                            logger.debug("Could not read display for field %s", field_name)

                    signatures.append(SignatureInfo(
                        field_name=field_name,
                        page=page_num + 1,  # 1-indexed for display
                        signer=signer if signer else "Signature numérique",
                        signed_on=signed_on,
                        is_valid=None,  # PyMuPDF doesn't validate signatures
                    ))

        return signatures

    def has_signatures(self) -> bool:
        """Check if the document contains any digital signatures."""
        return len(self.get_signatures()) > 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
