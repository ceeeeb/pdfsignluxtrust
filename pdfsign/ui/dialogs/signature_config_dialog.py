"""Signature appearance configuration dialog."""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QGroupBox,
    QRadioButton,
    QButtonGroup,
    QFileDialog,
    QSpinBox,
    QCheckBox,
    QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from pdfsign.core.signature_manager import SignatureAppearance, SignatureAppearanceType


class SignatureConfigDialog(QDialog):
    """Dialog for configuring signature appearance."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._appearance = SignatureAppearance()
        self._image_path: Path | None = None

        self.setWindowTitle("Configuration de la signature")
        self.setMinimumWidth(500)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create the UI."""
        layout = QVBoxLayout(self)

        # Appearance type selection
        type_group = QGroupBox("Type d'apparence")
        type_layout = QVBoxLayout(type_group)

        self._type_group = QButtonGroup(self)

        self._text_radio = QRadioButton("Texte uniquement")
        self._text_radio.setChecked(True)
        self._type_group.addButton(self._text_radio, SignatureAppearanceType.TEXT.value)
        type_layout.addWidget(self._text_radio)

        self._image_radio = QRadioButton("Image uniquement")
        self._type_group.addButton(self._image_radio, SignatureAppearanceType.IMAGE.value)
        type_layout.addWidget(self._image_radio)

        self._both_radio = QRadioButton("Texte et image")
        self._type_group.addButton(self._both_radio, SignatureAppearanceType.TEXT_AND_IMAGE.value)
        type_layout.addWidget(self._both_radio)

        self._type_group.idToggled.connect(self._on_type_changed)

        layout.addWidget(type_group)

        # Text options
        self._text_group = QGroupBox("Options texte")
        text_layout = QVBoxLayout(self._text_group)

        # Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Nom:"))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Nom du signataire")
        name_layout.addWidget(self._name_edit)
        text_layout.addLayout(name_layout)

        # Reason
        reason_layout = QHBoxLayout()
        reason_layout.addWidget(QLabel("Raison:"))
        self._reason_edit = QLineEdit()
        self._reason_edit.setPlaceholderText("Raison de la signature")
        reason_layout.addWidget(self._reason_edit)
        text_layout.addLayout(reason_layout)

        # Location
        location_layout = QHBoxLayout()
        location_layout.addWidget(QLabel("Lieu:"))
        self._location_edit = QLineEdit()
        self._location_edit.setPlaceholderText("Lieu de signature")
        location_layout.addWidget(self._location_edit)
        text_layout.addLayout(location_layout)

        # Options row
        options_layout = QHBoxLayout()

        self._date_checkbox = QCheckBox("Inclure la date")
        self._date_checkbox.setChecked(True)
        options_layout.addWidget(self._date_checkbox)

        options_layout.addWidget(QLabel("Taille police:"))
        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(6, 24)
        self._font_size_spin.setValue(10)
        options_layout.addWidget(self._font_size_spin)

        options_layout.addStretch()
        text_layout.addLayout(options_layout)

        layout.addWidget(self._text_group)

        # Image options
        self._image_group = QGroupBox("Image de signature")
        image_layout = QVBoxLayout(self._image_group)

        # Image selection
        select_layout = QHBoxLayout()
        self._image_path_label = QLabel("Aucune image selectionnee")
        self._image_path_label.setStyleSheet("color: gray;")
        select_layout.addWidget(self._image_path_label, 1)

        self._select_image_btn = QPushButton("Parcourir...")
        self._select_image_btn.clicked.connect(self._on_select_image)
        select_layout.addWidget(self._select_image_btn)

        self._clear_image_btn = QPushButton("Effacer")
        self._clear_image_btn.clicked.connect(self._on_clear_image)
        self._clear_image_btn.setEnabled(False)
        select_layout.addWidget(self._clear_image_btn)

        image_layout.addLayout(select_layout)

        # Image preview
        self._preview_frame = QFrame()
        self._preview_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        self._preview_frame.setMinimumHeight(100)
        preview_layout = QVBoxLayout(self._preview_frame)

        self._preview_label = QLabel("Apercu")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet("color: gray;")
        preview_layout.addWidget(self._preview_label)

        image_layout.addWidget(self._preview_frame)

        self._image_group.setEnabled(False)
        layout.addWidget(self._image_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._on_ok)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)

    def _on_type_changed(self, button_id: int, checked: bool) -> None:
        """Handle appearance type change."""
        if not checked:
            return

        try:
            app_type = SignatureAppearanceType(button_id)
        except ValueError:
            return

        # Enable/disable sections based on type
        self._text_group.setEnabled(
            app_type in (SignatureAppearanceType.TEXT, SignatureAppearanceType.TEXT_AND_IMAGE)
        )
        self._image_group.setEnabled(
            app_type in (SignatureAppearanceType.IMAGE, SignatureAppearanceType.TEXT_AND_IMAGE)
        )

    def _update_image_preview(self, image_path: Path) -> None:
        """Load and display an image preview scaled to fit."""
        pixmap = QPixmap(str(image_path))
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                200, 80,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self._preview_label.setPixmap(scaled)
        else:
            self._preview_label.setText("Impossible de charger l'image")

    def _on_select_image(self) -> None:
        """Handle image selection."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selectionner une image de signature",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp);;Tous les fichiers (*)"
        )

        if file_path:
            self._image_path = Path(file_path)
            self._image_path_label.setText(self._image_path.name)
            self._image_path_label.setStyleSheet("")
            self._clear_image_btn.setEnabled(True)
            self._update_image_preview(self._image_path)

    def _on_clear_image(self) -> None:
        """Clear selected image."""
        self._image_path = None
        self._image_path_label.setText("Aucune image selectionnee")
        self._image_path_label.setStyleSheet("color: gray;")
        self._clear_image_btn.setEnabled(False)
        self._preview_label.clear()
        self._preview_label.setText("Apercu")
        self._preview_label.setStyleSheet("color: gray;")

    def _on_ok(self) -> None:
        """Handle OK button click."""
        # Determine appearance type
        checked_id = self._type_group.checkedId()
        try:
            self._appearance.type = SignatureAppearanceType(checked_id)
        except ValueError:
            self._appearance.type = SignatureAppearanceType.TEXT

        # Collect text options
        self._appearance.name = self._name_edit.text()
        self._appearance.reason = self._reason_edit.text()
        self._appearance.location = self._location_edit.text()
        self._appearance.include_date = self._date_checkbox.isChecked()
        self._appearance.font_size = self._font_size_spin.value()

        # Collect image options
        self._appearance.image_path = self._image_path

        self.accept()

    def get_appearance(self) -> SignatureAppearance:
        """Get the configured signature appearance."""
        return self._appearance

    def set_appearance(self, appearance: SignatureAppearance) -> None:
        """Set initial appearance values."""
        self._appearance = appearance

        # Set type
        if appearance.type == SignatureAppearanceType.TEXT:
            self._text_radio.setChecked(True)
        elif appearance.type == SignatureAppearanceType.IMAGE:
            self._image_radio.setChecked(True)
        else:
            self._both_radio.setChecked(True)

        # Set text options
        self._name_edit.setText(appearance.name)
        self._reason_edit.setText(appearance.reason)
        self._location_edit.setText(appearance.location)
        self._date_checkbox.setChecked(appearance.include_date)
        self._font_size_spin.setValue(appearance.font_size)

        # Set image
        if appearance.image_path:
            self._image_path = appearance.image_path
            self._image_path_label.setText(appearance.image_path.name)
            self._clear_image_btn.setEnabled(True)
            self._update_image_preview(appearance.image_path)
