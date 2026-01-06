"""PDF viewer widget with signature overlay support."""

from PySide6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import (
    QWheelEvent,
    QMouseEvent,
    QPainter,
    QPixmap,
)

from pdfsign.core.pdf_document import PDFDocument
from pdfsign.ui.signature_rect import SignatureRectItem
from pdfsign.utils.coordinates import qt_to_pdf_rect, PDFRect


class PDFViewer(QGraphicsView):
    """
    PDF viewer with zoom, pan, and signature placement support.

    Signals:
        page_changed(int): Emitted when current page changes.
        zoom_changed(float): Emitted when zoom level changes.
        signature_position_changed(PDFRect): Emitted when signature rect moves.
    """

    page_changed = Signal(int)
    zoom_changed = Signal(float)
    signature_position_changed = Signal(object)  # PDFRect

    MIN_ZOOM = 0.25
    MAX_ZOOM = 4.0
    ZOOM_STEP = 0.1

    def __init__(self, parent=None):
        super().__init__(parent)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._document: PDFDocument | None = None
        self._current_page = 0
        self._zoom = 1.0

        self._page_item: QGraphicsPixmapItem | None = None
        self._signature_rect: SignatureRectItem | None = None
        self._signature_visible = False

        # Panning state
        self._panning = False
        self._pan_start: QPointF | None = None

        self._setup_view()

    def _setup_view(self) -> None:
        """Configure view settings."""
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setBackgroundBrush(Qt.GlobalColor.darkGray)

    def set_document(self, document: PDFDocument) -> None:
        """
        Set the PDF document to display.

        Args:
            document: Open PDFDocument instance.
        """
        self._document = document
        self._current_page = 0
        self._render_current_page()

    def clear_document(self) -> None:
        """Clear the current document."""
        self._document = None
        self._scene.clear()
        self._page_item = None
        self._signature_rect = None
        self._signature_visible = False

    def _render_current_page(self) -> None:
        """Render and display the current page."""
        if not self._document:
            return

        # Clear previous page
        self._scene.clear()
        self._signature_rect = None

        # Render page at current zoom
        pixmap = self._document.render_page(self._current_page, self._zoom)

        # Add to scene
        self._page_item = QGraphicsPixmapItem(pixmap)
        self._scene.addItem(self._page_item)

        # Update scene rect
        self._scene.setSceneRect(self._page_item.boundingRect())

        # Restore signature rect if visible
        if self._signature_visible:
            self._add_signature_rect()

        self.page_changed.emit(self._current_page)

    def _add_signature_rect(self) -> None:
        """Add the signature rectangle overlay."""
        if not self._page_item:
            return

        page_rect = self._page_item.boundingRect()

        # Default position: bottom-right area
        default_width = 200 * self._zoom
        default_height = 80 * self._zoom
        default_x = page_rect.width() - default_width - 50 * self._zoom
        default_y = page_rect.height() - default_height - 50 * self._zoom

        self._signature_rect = SignatureRectItem(
            default_x, default_y, default_width, default_height
        )
        self._scene.addItem(self._signature_rect)
        self._signature_rect.setSelected(True)

    # Navigation

    @property
    def current_page(self) -> int:
        """Get current page number (0-indexed)."""
        return self._current_page

    @property
    def page_count(self) -> int:
        """Get total page count."""
        if not self._document:
            return 0
        return self._document.page_count

    def go_to_page(self, page_num: int) -> None:
        """Navigate to a specific page."""
        if not self._document:
            return

        if 0 <= page_num < self._document.page_count:
            self._current_page = page_num
            self._render_current_page()

    def next_page(self) -> None:
        """Go to next page."""
        self.go_to_page(self._current_page + 1)

    def previous_page(self) -> None:
        """Go to previous page."""
        self.go_to_page(self._current_page - 1)

    # Zoom

    @property
    def zoom(self) -> float:
        """Get current zoom level."""
        return self._zoom

    def set_zoom(self, zoom: float) -> None:
        """Set zoom level."""
        zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, zoom))
        if zoom != self._zoom:
            self._zoom = zoom
            self._render_current_page()
            self.zoom_changed.emit(self._zoom)

    def zoom_in(self) -> None:
        """Increase zoom level."""
        self.set_zoom(self._zoom + self.ZOOM_STEP)

    def zoom_out(self) -> None:
        """Decrease zoom level."""
        self.set_zoom(self._zoom - self.ZOOM_STEP)

    def zoom_fit_width(self) -> None:
        """Zoom to fit page width in viewport."""
        if not self._document:
            return

        page_info = self._document.get_page_info(self._current_page)
        viewport_width = self.viewport().width() - 20  # Margin

        new_zoom = viewport_width / page_info.width
        self.set_zoom(new_zoom)

    def zoom_fit_page(self) -> None:
        """Zoom to fit entire page in viewport."""
        if not self._document:
            return

        page_info = self._document.get_page_info(self._current_page)
        viewport = self.viewport()
        viewport_width = viewport.width() - 20
        viewport_height = viewport.height() - 20

        zoom_w = viewport_width / page_info.width
        zoom_h = viewport_height / page_info.height

        self.set_zoom(min(zoom_w, zoom_h))

    def zoom_reset(self) -> None:
        """Reset zoom to 100%."""
        self.set_zoom(1.0)

    # Signature

    def show_signature_rect(self) -> None:
        """Show the signature placement rectangle."""
        self._signature_visible = True
        if not self._signature_rect and self._page_item:
            self._add_signature_rect()

    def hide_signature_rect(self) -> None:
        """Hide the signature placement rectangle."""
        self._signature_visible = False
        if self._signature_rect:
            self._scene.removeItem(self._signature_rect)
            self._signature_rect = None

    def get_signature_position(self) -> PDFRect | None:
        """
        Get the signature rectangle position in PDF coordinates.

        Returns:
            PDFRect in PDF coordinate system, or None if not set.
        """
        if not self._signature_rect or not self._document:
            return None

        # Get rect in scene coordinates
        scene_rect = self._signature_rect.get_scene_rect()

        # Get page dimensions
        page_info = self._document.get_page_info(self._current_page)

        # Convert to PDF coordinates
        return qt_to_pdf_rect(scene_rect, page_info.height, self._zoom)

    def set_signature_position(self, pdf_rect: PDFRect) -> None:
        """
        Set the signature rectangle from PDF coordinates.

        Args:
            pdf_rect: Position in PDF coordinate system.
        """
        if not self._document:
            return

        from pdfsign.utils.coordinates import pdf_to_qt_rect

        page_info = self._document.get_page_info(self._current_page)
        qt_rect = pdf_to_qt_rect(pdf_rect, page_info.height, self._zoom)

        self._signature_visible = True
        if self._signature_rect:
            self._signature_rect.setRect(qt_rect)
        else:
            self._add_signature_rect()
            if self._signature_rect:
                self._signature_rect.setRect(qt_rect)

    # Events

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Handle mouse wheel for zoom."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Zoom with Ctrl+Wheel
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            # Normal scroll
            super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press for panning."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move for panning."""
        if self._panning and self._pan_start:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()

            # Scroll the view
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self._pan_start = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
