"""
Screen Translator — Entry Point.

A desktop application that monitors a screen region, extracts text via OCR,
and displays real-time translations in a transparent overlay window.
"""

from __future__ import annotations

import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt

from utils.logger import setup_logging, get_logger


def _show_fatal_error(message: str) -> None:
    """Display a fatal error message box. Works even before QApplication."""
    try:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        QMessageBox.critical(None, "Screen Translator - Fatal Error", message)
    except Exception:
        print(f"FATAL ERROR: {message}", file=sys.stderr)


def main() -> None:
    """Initialize and launch the Screen Translator application."""
    try:
        setup_logging()
    except Exception:
        pass

    logger = get_logger(__name__)
    logger.info("Starting Screen Translator...")

    try:
        app = QApplication(sys.argv)
        app.setApplicationName("Screen Translator")
        app.setOrganizationName("ScreenTranslator")
        app.setStyle("Fusion")

        from gui.main_window import MainWindow

        window = MainWindow()
        window.show()

        logger.info("Application started.")
        sys.exit(app.exec())
    except Exception as e:
        logger.exception("Fatal error during startup")
        _show_fatal_error(f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}")


if __name__ == "__main__":
    main()
