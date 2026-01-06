"""Coordinate conversion between Qt and PDF coordinate systems."""

from dataclasses import dataclass
from PySide6.QtCore import QRectF, QPointF


@dataclass
class PDFRect:
    """Rectangle in PDF coordinates (origin bottom-left, Y up)."""
    x1: float  # Left
    y1: float  # Bottom
    x2: float  # Right
    y2: float  # Top

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    def as_tuple(self) -> tuple[float, float, float, float]:
        """Return as (x1, y1, x2, y2) tuple for pyHanko."""
        return (self.x1, self.y1, self.x2, self.y2)


def qt_to_pdf_rect(
    qt_rect: QRectF,
    page_height: float,
    zoom: float = 1.0
) -> PDFRect:
    """
    Convert a Qt rectangle to PDF coordinates.

    Qt coordinate system:
        - Origin at top-left
        - Y increases downward

    PDF coordinate system:
        - Origin at bottom-left
        - Y increases upward

    Args:
        qt_rect: Rectangle in Qt coordinates (screen pixels).
        page_height: Height of the PDF page in PDF points.
        zoom: Current zoom factor applied to the Qt view.

    Returns:
        PDFRect in PDF coordinate system.
    """
    # Remove zoom factor to get PDF points
    x1 = qt_rect.left() / zoom
    x2 = qt_rect.right() / zoom

    # Invert Y axis: Qt top -> PDF bottom
    # Qt bottom of rect -> PDF y1 (bottom)
    # Qt top of rect -> PDF y2 (top)
    y1 = page_height - (qt_rect.bottom() / zoom)
    y2 = page_height - (qt_rect.top() / zoom)

    return PDFRect(x1=x1, y1=y1, x2=x2, y2=y2)


def pdf_to_qt_rect(
    pdf_rect: PDFRect,
    page_height: float,
    zoom: float = 1.0
) -> QRectF:
    """
    Convert a PDF rectangle to Qt coordinates.

    Args:
        pdf_rect: Rectangle in PDF coordinates.
        page_height: Height of the PDF page in PDF points.
        zoom: Current zoom factor to apply.

    Returns:
        QRectF in Qt coordinate system.
    """
    # Apply zoom and invert Y axis
    left = pdf_rect.x1 * zoom
    right = pdf_rect.x2 * zoom

    # PDF y2 (top) -> Qt top
    # PDF y1 (bottom) -> Qt bottom
    top = (page_height - pdf_rect.y2) * zoom
    bottom = (page_height - pdf_rect.y1) * zoom

    return QRectF(left, top, right - left, bottom - top)


def qt_point_to_pdf(
    point: QPointF,
    page_height: float,
    zoom: float = 1.0
) -> tuple[float, float]:
    """
    Convert a Qt point to PDF coordinates.

    Args:
        point: Point in Qt coordinates.
        page_height: Height of the PDF page in PDF points.
        zoom: Current zoom factor.

    Returns:
        Tuple (x, y) in PDF coordinates.
    """
    x = point.x() / zoom
    y = page_height - (point.y() / zoom)
    return (x, y)


def adjust_rect_for_rotation(
    pdf_rect: PDFRect,
    page_width: float,
    page_height: float,
    rotation: int
) -> PDFRect:
    """
    Adjust rectangle coordinates for page rotation.

    Args:
        pdf_rect: Original rectangle in PDF coordinates.
        page_width: Width of the unrotated page.
        page_height: Height of the unrotated page.
        rotation: Page rotation in degrees (0, 90, 180, 270).

    Returns:
        Adjusted PDFRect accounting for rotation.
    """
    if rotation == 0:
        return pdf_rect

    x1, y1, x2, y2 = pdf_rect.x1, pdf_rect.y1, pdf_rect.x2, pdf_rect.y2

    if rotation == 90:
        # Rotate 90 degrees clockwise
        return PDFRect(
            x1=y1,
            y1=page_width - x2,
            x2=y2,
            y2=page_width - x1
        )
    elif rotation == 180:
        # Rotate 180 degrees
        return PDFRect(
            x1=page_width - x2,
            y1=page_height - y2,
            x2=page_width - x1,
            y2=page_height - y1
        )
    elif rotation == 270:
        # Rotate 270 degrees clockwise (90 counter-clockwise)
        return PDFRect(
            x1=page_height - y2,
            y1=x1,
            x2=page_height - y1,
            y2=x2
        )

    return pdf_rect
