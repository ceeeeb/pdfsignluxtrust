"""Main application window."""

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QToolBar,
    QStatusBar,
    QFileDialog,
    QMessageBox,
    QLabel,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QProgressDialog,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction, QKeySequence

from pdfsign.core.pdf_document import PDFDocument
from pdfsign.core.signature_manager import (
    SignatureManager, SignatureConfig, SignatureAppearance, SignaturePosition,
)
from pdfsign.utils.settings import save_signature_appearance, load_signature_appearance
from pdfsign.crypto.pkcs11_manager import PKCS11Manager, PKCS11Error
from pdfsign.ui.pdf_viewer import PDFViewer
from pdfsign.ui.dialogs.pin_dialog import TokenSelectionDialog
from pdfsign.ui.dialogs.signature_config_dialog import SignatureConfigDialog


class SignatureWorker(QThread):
    """Worker thread for PDF signing operations."""

    progress = Signal(str)
    finished = Signal(Path)
    error = Signal(str)

    def __init__(
        self,
        signature_manager: SignatureManager,
        input_path: Path,
        output_path: Path,
        pin: str,
        config: SignatureConfig,
        alias: str | None = None,
        slot: int = 0,
    ):
        super().__init__()
        self._manager = signature_manager
        self._input_path = input_path
        self._output_path = output_path
        self._pin = pin
        self._config = config
        self._alias = alias
        self._slot = slot

    def run(self):
        try:
            self.progress.emit("Signature en cours...")
            result = self._manager.sign_pdf(
                self._input_path,
                self._output_path,
                self._pin,
                self._config,
                self._alias,
                self._slot,
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self._document = PDFDocument()
        self._signature_manager = SignatureManager()
        self._pkcs11_manager: PKCS11Manager | None = None
        self._current_file: Path | None = None

        # Load saved signature appearance or use default
        saved_appearance = load_signature_appearance()
        self._signature_appearance = saved_appearance if saved_appearance else SignatureAppearance()

        self.setWindowTitle("PDF Signer - LuxTrust")
        self.setMinimumSize(900, 700)

        self._setup_ui()
        self._setup_toolbar()
        self._setup_statusbar()
        self._setup_connections()

        self._init_pkcs11()

    def _setup_ui(self) -> None:
        """Create the main UI."""
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # PDF Viewer
        self._viewer = PDFViewer()
        layout.addWidget(self._viewer)

        # Bottom control bar
        control_bar = QWidget()
        control_layout = QHBoxLayout(control_bar)
        control_layout.setContentsMargins(10, 5, 10, 5)

        # Page navigation
        self._prev_btn = QPushButton("<")
        self._prev_btn.setFixedWidth(30)
        self._prev_btn.clicked.connect(self._viewer.previous_page)
        control_layout.addWidget(self._prev_btn)

        self._page_spin = QSpinBox()
        self._page_spin.setMinimum(1)
        self._page_spin.valueChanged.connect(self._on_page_spin_changed)
        control_layout.addWidget(self._page_spin)

        self._page_count_label = QLabel("/ 0")
        control_layout.addWidget(self._page_count_label)

        self._next_btn = QPushButton(">")
        self._next_btn.setFixedWidth(30)
        self._next_btn.clicked.connect(self._viewer.next_page)
        control_layout.addWidget(self._next_btn)

        control_layout.addSpacing(20)

        # Zoom controls
        self._zoom_out_btn = QPushButton("-")
        self._zoom_out_btn.setFixedWidth(30)
        self._zoom_out_btn.clicked.connect(self._viewer.zoom_out)
        control_layout.addWidget(self._zoom_out_btn)

        self._zoom_label = QLabel("100%")
        self._zoom_label.setMinimumWidth(50)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        control_layout.addWidget(self._zoom_label)

        self._zoom_in_btn = QPushButton("+")
        self._zoom_in_btn.setFixedWidth(30)
        self._zoom_in_btn.clicked.connect(self._viewer.zoom_in)
        control_layout.addWidget(self._zoom_in_btn)

        self._fit_width_btn = QPushButton("Largeur")
        self._fit_width_btn.clicked.connect(self._viewer.zoom_fit_width)
        control_layout.addWidget(self._fit_width_btn)

        control_layout.addStretch()

        # Signature button
        self._sign_btn = QPushButton("Signer le document")
        self._sign_btn.setEnabled(False)
        self._sign_btn.clicked.connect(self._on_sign_clicked)
        control_layout.addWidget(self._sign_btn)

        layout.addWidget(control_bar)

    def _setup_toolbar(self) -> None:
        """Create the toolbar."""
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Open action
        self._open_action = QAction("Ouvrir", self)
        self._open_action.setShortcut(QKeySequence.StandardKey.Open)
        self._open_action.triggered.connect(self._on_open)
        toolbar.addAction(self._open_action)

        toolbar.addSeparator()

        # Signature placement
        self._place_sig_action = QAction("Placer signature", self)
        self._place_sig_action.setCheckable(True)
        self._place_sig_action.setEnabled(False)
        self._place_sig_action.triggered.connect(self._on_place_signature)
        toolbar.addAction(self._place_sig_action)

        # Signature config
        self._config_sig_action = QAction("Configurer...", self)
        self._config_sig_action.triggered.connect(self._on_config_signature)
        toolbar.addAction(self._config_sig_action)

        toolbar.addSeparator()

        # Token info
        self._token_action = QAction("Token: Non connecte", self)
        self._token_action.triggered.connect(self._on_select_token)
        toolbar.addAction(self._token_action)

    def _setup_statusbar(self) -> None:
        """Create the status bar."""
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)

        self._status_label = QLabel("Pret")
        self._statusbar.addWidget(self._status_label, 1)

    def _setup_connections(self) -> None:
        """Connect signals."""
        self._viewer.page_changed.connect(self._on_page_changed)
        self._viewer.zoom_changed.connect(self._on_zoom_changed)

    def _init_pkcs11(self) -> None:
        """Initialize PKCS#11 manager."""
        try:
            self._pkcs11_manager = PKCS11Manager()
            self._token_action.setText("Token: Pret")
            self._status_label.setText(
                f"Bibliotheque PKCS#11: {self._pkcs11_manager.library_path}"
            )
        except PKCS11Error as e:
            self._token_action.setText("Token: Non disponible")
            self._status_label.setText(f"PKCS#11: {e}")

    # File operations

    def _on_open(self) -> None:
        """Handle open file action."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Ouvrir un PDF",
            "",
            "Documents PDF (*.pdf);;Tous les fichiers (*)"
        )

        if file_path:
            self._open_file(Path(file_path))

    def _open_file(self, path: Path) -> None:
        """Open a PDF file."""
        try:
            self._document.close()
            self._document.open(path)
            self._current_file = path

            self._viewer.set_document(self._document)

            # Update UI
            self._page_spin.setMaximum(self._document.page_count)
            self._page_count_label.setText(f"/ {self._document.page_count}")
            self._place_sig_action.setEnabled(True)
            self._sign_btn.setEnabled(True)

            self.setWindowTitle(f"PDF Signer - {path.name}")
            self._status_label.setText(f"Ouvert: {path.name}")

            # Check for existing signatures
            self._check_existing_signatures()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Impossible d'ouvrir le fichier:\n{e}"
            )

    def _check_existing_signatures(self) -> None:
        """Check and notify about existing digital signatures."""
        signatures = self._document.get_signatures()
        if not signatures:
            return

        # Build message with signature details
        count = len(signatures)
        if count == 1:
            title = "Signature numerique detectee"
            message = "Ce document contient une signature numerique:\n\n"
        else:
            title = f"{count} signatures numeriques detectees"
            message = f"Ce document contient {count} signatures numeriques:\n\n"

        for i, sig in enumerate(signatures, 1):
            message += f"{i}. {sig.signer}\n"
            message += f"   Champ: {sig.field_name} (page {sig.page})\n"
            if sig.signed_on:
                message += f"   Date: {sig.signed_on}\n"
            message += "\n"

        message += "Ajouter une nouvelle signature conservera les signatures existantes."

        QMessageBox.information(self, title, message)

    # Navigation

    def _on_page_changed(self, page: int) -> None:
        """Handle page change."""
        self._page_spin.blockSignals(True)
        self._page_spin.setValue(page + 1)
        self._page_spin.blockSignals(False)

    def _on_page_spin_changed(self, value: int) -> None:
        """Handle page spin change."""
        self._viewer.go_to_page(value - 1)

    def _on_zoom_changed(self, zoom: float) -> None:
        """Handle zoom change."""
        self._zoom_label.setText(f"{int(zoom * 100)}%")

    # Signature

    def _on_place_signature(self, checked: bool) -> None:
        """Toggle signature placement mode."""
        if checked:
            self._viewer.show_signature_rect()
            self._status_label.setText(
                "Placez et redimensionnez le rectangle de signature"
            )
        else:
            self._viewer.hide_signature_rect()
            self._status_label.setText("Pret")

    def _on_config_signature(self) -> None:
        """Open signature configuration dialog."""
        dialog = SignatureConfigDialog(self)
        dialog.set_appearance(self._signature_appearance)

        if dialog.exec():
            self._signature_appearance = dialog.get_appearance()
            # Save configuration for future sessions
            save_signature_appearance(self._signature_appearance)
            self._status_label.setText("Configuration de signature sauvegardee")

    def _on_select_token(self) -> None:
        """Open token selection dialog."""
        if not self._pkcs11_manager:
            QMessageBox.warning(
                self,
                "PKCS#11 non disponible",
                "La bibliotheque PKCS#11 n'est pas disponible.\n"
                "Verifiez que LuxTrust Middleware est installe."
            )
            return

        dialog = TokenSelectionDialog(self._pkcs11_manager, self)
        if dialog.exec():
            token, cert, pin = dialog.get_selection()
            if token and cert:
                self._token_action.setText(f"Token: {cert.subject_cn}")

    def _on_sign_clicked(self) -> None:
        """Handle sign button click."""
        if not self._document.is_open or not self._current_file:
            return

        if not self._pkcs11_manager:
            QMessageBox.warning(
                self,
                "PKCS#11 non disponible",
                "La bibliotheque PKCS#11 n'est pas disponible."
            )
            return

        # Ensure signature rect is visible
        if not self._place_sig_action.isChecked():
            self._place_sig_action.setChecked(True)
            self._on_place_signature(True)

        # Get signature position
        position = self._viewer.get_signature_position()
        if not position:
            QMessageBox.warning(
                self,
                "Position requise",
                "Veuillez placer le rectangle de signature sur le document."
            )
            return

        # Select token and certificate
        dialog = TokenSelectionDialog(self._pkcs11_manager, self)
        if not dialog.exec():
            return

        token, cert, pin = dialog.get_selection()
        if not token or not cert:
            return

        # Get output file path
        default_name = self._current_file.stem + "_signe.pdf"
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer le PDF signe",
            str(self._current_file.parent / default_name),
            "Documents PDF (*.pdf)"
        )

        if not output_path:
            return

        sig_position = SignaturePosition(
            page=self._viewer.current_page + 1,
            x=position.x1,
            y=position.y1,
            width=position.width,
            height=position.height,
        )
        config = SignatureConfig(
            position=sig_position,
            appearance=self._signature_appearance,
        )

        # Show progress dialog
        progress = QProgressDialog("Signature en cours...", "Annuler", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        # Run signing in worker thread
        self._worker = SignatureWorker(
            self._signature_manager,
            self._current_file,
            Path(output_path),
            pin,
            config,
            alias=cert.label,
            slot=token.slot_id,
        )
        self._worker.finished.connect(lambda p: self._on_signing_finished(p, progress))
        self._worker.error.connect(lambda e: self._on_signing_error(e, progress))
        self._worker.start()

    def _on_signing_finished(self, output_path: Path, progress: QProgressDialog) -> None:
        """Handle successful signing."""
        progress.close()
        QMessageBox.information(
            self,
            "Signature reussie",
            f"Le document a ete signe avec succes:\n{output_path}"
        )
        self._status_label.setText(f"Signe: {output_path.name}")

        # Ask to open signed document
        reply = QMessageBox.question(
            self,
            "Ouvrir le document",
            "Voulez-vous ouvrir le document signe?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._open_file(output_path)

    def _on_signing_error(self, error: str, progress: QProgressDialog) -> None:
        """Handle signing error."""
        progress.close()
        QMessageBox.critical(
            self,
            "Erreur de signature",
            f"La signature a echoue:\n{error}"
        )
        self._status_label.setText("Erreur de signature")

    def closeEvent(self, event) -> None:
        """Handle window close."""
        self._document.close()
        super().closeEvent(event)
