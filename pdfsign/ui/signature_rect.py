"""Draggable and resizable signature rectangle overlay."""

from enum import Enum, auto
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsItem
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPen, QBrush, QColor, QPainter, QCursor


class ResizeHandle(Enum):
    """Resize handle positions."""
    NONE = auto()
    TOP_LEFT = auto()
    TOP_RIGHT = auto()
    BOTTOM_LEFT = auto()
    BOTTOM_RIGHT = auto()
    TOP = auto()
    BOTTOM = auto()
    LEFT = auto()
    RIGHT = auto()


class SignatureRectItem(QGraphicsRectItem):
    """
    A draggable and resizable rectangle for signature placement.

    Features:
    - Drag to move
    - Resize from corners and edges
    - Minimum size constraint
    - Visual feedback on hover/selection
    """

    HANDLE_SIZE = 8
    MIN_WIDTH = 100
    MIN_HEIGHT = 50

    def __init__(
        self,
        x: float = 0,
        y: float = 0,
        width: float = 200,
        height: float = 80,
        parent: QGraphicsItem | None = None
    ):
        super().__init__(x, y, width, height, parent)

        self._current_handle = ResizeHandle.NONE
        self._drag_start_pos: QPointF | None = None
        self._drag_start_rect: QRectF | None = None

        # Make item interactive
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

        # Visual style
        self._setup_style()

    def _setup_style(self) -> None:
        """Configure the visual appearance."""
        # Border
        pen = QPen(QColor(0, 120, 212))  # Blue
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DashLine)
        self.setPen(pen)

        # Fill
        fill_color = QColor(0, 120, 212, 40)  # Semi-transparent blue
        self.setBrush(QBrush(fill_color))

    def _get_handle_rects(self) -> dict[ResizeHandle, QRectF]:
        """Get rectangles for all resize handles."""
        rect = self.rect()
        hs = self.HANDLE_SIZE
        hhs = hs / 2  # Half handle size

        return {
            ResizeHandle.TOP_LEFT: QRectF(
                rect.left() - hhs, rect.top() - hhs, hs, hs
            ),
            ResizeHandle.TOP_RIGHT: QRectF(
                rect.right() - hhs, rect.top() - hhs, hs, hs
            ),
            ResizeHandle.BOTTOM_LEFT: QRectF(
                rect.left() - hhs, rect.bottom() - hhs, hs, hs
            ),
            ResizeHandle.BOTTOM_RIGHT: QRectF(
                rect.right() - hhs, rect.bottom() - hhs, hs, hs
            ),
            ResizeHandle.TOP: QRectF(
                rect.center().x() - hhs, rect.top() - hhs, hs, hs
            ),
            ResizeHandle.BOTTOM: QRectF(
                rect.center().x() - hhs, rect.bottom() - hhs, hs, hs
            ),
            ResizeHandle.LEFT: QRectF(
                rect.left() - hhs, rect.center().y() - hhs, hs, hs
            ),
            ResizeHandle.RIGHT: QRectF(
                rect.right() - hhs, rect.center().y() - hhs, hs, hs
            ),
        }

    def _get_handle_at(self, pos: QPointF) -> ResizeHandle:
        """Determine which handle (if any) is at the given position."""
        for handle, rect in self._get_handle_rects().items():
            if rect.contains(pos):
                return handle
        return ResizeHandle.NONE

    def _get_cursor_for_handle(self, handle: ResizeHandle) -> Qt.CursorShape:
        """Get the appropriate cursor for a resize handle."""
        cursor_map = {
            ResizeHandle.TOP_LEFT: Qt.CursorShape.SizeFDiagCursor,
            ResizeHandle.BOTTOM_RIGHT: Qt.CursorShape.SizeFDiagCursor,
            ResizeHandle.TOP_RIGHT: Qt.CursorShape.SizeBDiagCursor,
            ResizeHandle.BOTTOM_LEFT: Qt.CursorShape.SizeBDiagCursor,
            ResizeHandle.TOP: Qt.CursorShape.SizeVerCursor,
            ResizeHandle.BOTTOM: Qt.CursorShape.SizeVerCursor,
            ResizeHandle.LEFT: Qt.CursorShape.SizeHorCursor,
            ResizeHandle.RIGHT: Qt.CursorShape.SizeHorCursor,
            ResizeHandle.NONE: Qt.CursorShape.SizeAllCursor,
        }
        return cursor_map.get(handle, Qt.CursorShape.ArrowCursor)

    def boundingRect(self) -> QRectF:
        """Return bounding rect including handles."""
        rect = super().boundingRect()
        margin = self.HANDLE_SIZE
        return rect.adjusted(-margin, -margin, margin, margin)

    def paint(
        self,
        painter: QPainter,
        option,
        widget=None
    ) -> None:
        """Paint the rectangle and resize handles."""
        # Draw main rectangle
        super().paint(painter, option, widget)

        # Draw resize handles when selected
        if self.isSelected():
            painter.setPen(QPen(QColor(0, 120, 212), 1))
            painter.setBrush(QBrush(Qt.GlobalColor.white))

            for handle, rect in self._get_handle_rects().items():
                painter.drawRect(rect)

    def hoverMoveEvent(self, event) -> None:
        """Update cursor based on position."""
        handle = self._get_handle_at(event.pos())
        cursor = self._get_cursor_for_handle(handle)
        self.setCursor(QCursor(cursor))
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        """Reset cursor when leaving."""
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        """Handle mouse press for resize or move."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._current_handle = self._get_handle_at(event.pos())
            self._drag_start_pos = event.pos()
            self._drag_start_rect = self.rect()

            if self._current_handle != ResizeHandle.NONE:
                # Prevent default move behavior during resize
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        """Handle mouse move for resize."""
        if self._current_handle != ResizeHandle.NONE and self._drag_start_rect:
            self._resize_rect(event.pos())
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """Handle mouse release."""
        self._current_handle = ResizeHandle.NONE
        self._drag_start_pos = None
        self._drag_start_rect = None
        super().mouseReleaseEvent(event)

    def _resize_rect(self, current_pos: QPointF) -> None:
        """Resize the rectangle based on handle being dragged."""
        if not self._drag_start_rect or not self._drag_start_pos:
            return

        rect = QRectF(self._drag_start_rect)
        delta = current_pos - self._drag_start_pos

        # Apply resize based on handle
        if self._current_handle in (
            ResizeHandle.TOP_LEFT, ResizeHandle.TOP, ResizeHandle.TOP_RIGHT
        ):
            new_top = rect.top() + delta.y()
            if rect.bottom() - new_top >= self.MIN_HEIGHT:
                rect.setTop(new_top)

        if self._current_handle in (
            ResizeHandle.BOTTOM_LEFT, ResizeHandle.BOTTOM, ResizeHandle.BOTTOM_RIGHT
        ):
            new_bottom = rect.bottom() + delta.y()
            if new_bottom - rect.top() >= self.MIN_HEIGHT:
                rect.setBottom(new_bottom)

        if self._current_handle in (
            ResizeHandle.TOP_LEFT, ResizeHandle.LEFT, ResizeHandle.BOTTOM_LEFT
        ):
            new_left = rect.left() + delta.x()
            if rect.right() - new_left >= self.MIN_WIDTH:
                rect.setLeft(new_left)

        if self._current_handle in (
            ResizeHandle.TOP_RIGHT, ResizeHandle.RIGHT, ResizeHandle.BOTTOM_RIGHT
        ):
            new_right = rect.right() + delta.x()
            if new_right - rect.left() >= self.MIN_WIDTH:
                rect.setRight(new_right)

        self.setRect(rect)

    def constrain_to_bounds(self, bounds: QRectF) -> None:
        """Ensure the rectangle stays within given bounds."""
        rect = self.rect()
        pos = self.pos()

        # Calculate absolute position
        abs_rect = rect.translated(pos)

        # Constrain to bounds
        if abs_rect.left() < bounds.left():
            pos.setX(bounds.left() - rect.left())
        if abs_rect.right() > bounds.right():
            pos.setX(bounds.right() - rect.right())
        if abs_rect.top() < bounds.top():
            pos.setY(bounds.top() - rect.top())
        if abs_rect.bottom() > bounds.bottom():
            pos.setY(bounds.bottom() - rect.bottom())

        self.setPos(pos)

    def get_scene_rect(self) -> QRectF:
        """Get the rectangle in scene coordinates."""
        return self.mapRectToScene(self.rect())
