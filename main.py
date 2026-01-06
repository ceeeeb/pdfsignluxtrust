#!/usr/bin/env python3
"""PDF Signer Application - Entry point."""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from pdfsign.ui.main_window import MainWindow


def main():
    """Run the application."""
    # High DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("PDF Signer")
    app.setOrganizationName("PDFSign")

    # Set style
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
