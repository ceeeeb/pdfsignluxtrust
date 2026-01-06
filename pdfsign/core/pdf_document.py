"""PDF document wrapper using PyMuPDF."""

from pathlib import Path
from dataclasses import dataclass

import pymupdf
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import QByteArray


@dataclass
class PageInfo:
    """Information about a PDF page."""
    number: int
    width: float
    height: float
    rotation: int


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
        format: str = "png"
    ) -> bytes:
        """
        Render a page to bytes (PNG or JPEG).

        Args:
            page_num: Page number (0-indexed).
            zoom: Zoom factor.
            format: Output format ("png" or "jpeg").

        Returns:
            Image data as bytes.
        """
        if not self._doc:
            raise RuntimeError("No document is open")

        page = self._doc[page_num]
        mat = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        return pix.tobytes(format)

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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
