"""PIN entry dialog for PKCS#11 token authentication."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QGroupBox,
    QMessageBox,
)
from PySide6.QtCore import Qt

from pdfsign.crypto.pkcs11_manager import PKCS11Manager, TokenInfo, CertificateInfo, PKCS11Error


class TokenSelectionDialog(QDialog):
    """Dialog for selecting a PKCS#11 token and certificate."""

    def __init__(self, pkcs11_manager: PKCS11Manager, parent=None):
        super().__init__(parent)
        self._manager = pkcs11_manager
        self._tokens: list[TokenInfo] = []
        self._certificates: list[CertificateInfo] = []
        self._selected_token: TokenInfo | None = None
        self._selected_cert: CertificateInfo | None = None
        self._pin: str = ""

        self.setWindowTitle("Selection du token")
        self.setMinimumWidth(450)
        self._setup_ui()
        self._load_tokens()

    def _setup_ui(self) -> None:
        """Create the UI."""
        layout = QVBoxLayout(self)

        # Token selection
        token_group = QGroupBox("Token PKCS#11")
        token_layout = QVBoxLayout(token_group)

        self._token_combo = QComboBox()
        self._token_combo.currentIndexChanged.connect(self._on_token_changed)
        token_layout.addWidget(self._token_combo)

        self._token_info_label = QLabel()
        self._token_info_label.setStyleSheet("color: gray; font-size: 11px;")
        token_layout.addWidget(self._token_info_label)

        layout.addWidget(token_group)

        # PIN entry
        pin_group = QGroupBox("Authentification")
        pin_layout = QHBoxLayout(pin_group)

        pin_layout.addWidget(QLabel("PIN:"))
        self._pin_edit = QLineEdit()
        self._pin_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pin_edit.setPlaceholderText("Entrez votre PIN")
        self._pin_edit.returnPressed.connect(self._on_unlock_clicked)
        pin_layout.addWidget(self._pin_edit)

        self._unlock_btn = QPushButton("Deverrouiller")
        self._unlock_btn.clicked.connect(self._on_unlock_clicked)
        pin_layout.addWidget(self._unlock_btn)

        layout.addWidget(pin_group)

        # Certificate selection
        cert_group = QGroupBox("Certificat de signature")
        cert_layout = QVBoxLayout(cert_group)

        self._cert_combo = QComboBox()
        self._cert_combo.setEnabled(False)
        self._cert_combo.currentIndexChanged.connect(self._on_cert_changed)
        cert_layout.addWidget(self._cert_combo)

        self._cert_info_label = QLabel()
        self._cert_info_label.setStyleSheet("color: gray; font-size: 11px;")
        self._cert_info_label.setWordWrap(True)
        cert_layout.addWidget(self._cert_info_label)

        layout.addWidget(cert_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._cancel_btn = QPushButton("Annuler")
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)

        self._ok_btn = QPushButton("OK")
        self._ok_btn.setEnabled(False)
        self._ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self._ok_btn)

        layout.addLayout(btn_layout)

    def _load_tokens(self) -> None:
        """Load available PKCS#11 tokens."""
        try:
            self._tokens = self._manager.list_tokens()

            self._token_combo.clear()
            for token in self._tokens:
                self._token_combo.addItem(
                    f"{token.label} ({token.manufacturer})",
                    token.slot_id
                )

            if not self._tokens:
                self._token_combo.addItem("Aucun token detecte")
                self._token_combo.setEnabled(False)
                self._pin_edit.setEnabled(False)
                self._unlock_btn.setEnabled(False)

        except PKCS11Error as e:
            QMessageBox.warning(
                self,
                "Erreur PKCS#11",
                f"Impossible de lister les tokens:\n{e}"
            )

    def _on_token_changed(self, index: int) -> None:
        """Handle token selection change."""
        if index < 0 or index >= len(self._tokens):
            self._selected_token = None
            self._token_info_label.clear()
            return

        self._selected_token = self._tokens[index]
        self._token_info_label.setText(
            f"Modele: {self._selected_token.model} | "
            f"Serie: {self._selected_token.serial}"
        )

        # Reset certificate selection
        self._cert_combo.clear()
        self._cert_combo.setEnabled(False)
        self._certificates = []
        self._selected_cert = None
        self._ok_btn.setEnabled(False)

    def _on_unlock_clicked(self) -> None:
        """Handle unlock button click."""
        if not self._selected_token:
            return

        pin = self._pin_edit.text()
        if not pin:
            QMessageBox.warning(self, "PIN requis", "Veuillez entrer votre PIN.")
            return

        try:
            self._certificates = self._manager.list_certificates(
                self._selected_token.slot_id,
                pin
            )

            if not self._certificates:
                QMessageBox.warning(
                    self,
                    "Aucun certificat",
                    "Aucun certificat de signature trouve sur ce token."
                )
                return

            self._pin = pin
            self._cert_combo.clear()
            self._cert_combo.setEnabled(True)

            for cert in self._certificates:
                self._cert_combo.addItem(
                    f"{cert.subject_cn} ({cert.label})"
                )

            self._on_cert_changed(0)

        except PKCS11Error as e:
            error_msg = str(e)
            if "PIN" in error_msg.upper():
                QMessageBox.warning(
                    self,
                    "PIN incorrect",
                    "Le PIN entre est incorrect.\n"
                    "Attention: apres 3 tentatives incorrectes, le token sera bloque."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Erreur",
                    f"Impossible d'acceder au token:\n{e}"
                )

    def _on_cert_changed(self, index: int) -> None:
        """Handle certificate selection change."""
        if index < 0 or index >= len(self._certificates):
            self._selected_cert = None
            self._cert_info_label.clear()
            self._ok_btn.setEnabled(False)
            return

        self._selected_cert = self._certificates[index]
        self._cert_info_label.setText(
            f"Emetteur: {self._selected_cert.issuer_cn}\n"
            f"Valide: {self._selected_cert.not_before} - {self._selected_cert.not_after}"
        )
        self._ok_btn.setEnabled(True)

    def get_selection(self) -> tuple[TokenInfo | None, CertificateInfo | None, str]:
        """
        Get the selected token, certificate, and PIN.

        Returns:
            Tuple of (TokenInfo, CertificateInfo, PIN) or (None, None, "") if cancelled.
        """
        return self._selected_token, self._selected_cert, self._pin


class PINDialog(QDialog):
    """Simple PIN entry dialog."""

    MAX_ATTEMPTS = 3

    def __init__(self, token_label: str = "", parent=None):
        super().__init__(parent)
        self._token_label = token_label
        self._attempts = 0
        self._pin = ""

        self.setWindowTitle("Entrer le PIN")
        self.setMinimumWidth(300)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create the UI."""
        layout = QVBoxLayout(self)

        # Token info
        if self._token_label:
            label = QLabel(f"Token: {self._token_label}")
            label.setStyleSheet("font-weight: bold;")
            layout.addWidget(label)

        # PIN entry
        pin_layout = QHBoxLayout()
        pin_layout.addWidget(QLabel("PIN:"))

        self._pin_edit = QLineEdit()
        self._pin_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pin_edit.setPlaceholderText("Entrez votre PIN")
        self._pin_edit.returnPressed.connect(self.accept)
        pin_layout.addWidget(self._pin_edit)

        layout.addLayout(pin_layout)

        # Warning
        self._warning_label = QLabel()
        self._warning_label.setStyleSheet("color: orange;")
        self._warning_label.hide()
        layout.addWidget(self._warning_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)

    def show_error(self, message: str) -> None:
        """Show an error and increment attempt counter."""
        self._attempts += 1
        remaining = self.MAX_ATTEMPTS - self._attempts

        if remaining > 0:
            self._warning_label.setText(
                f"{message}\nTentatives restantes: {remaining}"
            )
            self._warning_label.show()
            self._pin_edit.clear()
            self._pin_edit.setFocus()
        else:
            QMessageBox.critical(
                self,
                "Token bloque",
                "Nombre maximum de tentatives atteint.\n"
                "Le token peut etre bloque."
            )
            self.reject()

    def get_pin(self) -> str:
        """Get the entered PIN."""
        return self._pin_edit.text()

    @property
    def attempts_remaining(self) -> int:
        """Get remaining PIN attempts."""
        return self.MAX_ATTEMPTS - self._attempts
