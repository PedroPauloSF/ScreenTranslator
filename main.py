"""
Screen Translator - Entry Point.

Modes:
    python main.py              Launcher dialog (choose mode)
    python main.py --continuous  Skip launcher, go to Continuous mode
    python main.py --study       Skip launcher, go to Study mode
"""

import sys
import traceback

from utils.logger import setup_logging, get_logger


def main() -> None:
    try:
        setup_logging()
    except Exception:
        pass

    logger = get_logger(__name__)
    logger.info("Starting Screen Translator...")

    study_cli = any(arg.lstrip("-").lower() == "study" for arg in sys.argv[1:])
    continuous_cli = any(arg.lstrip("-").lower() == "continuous" for arg in sys.argv[1:])

    try:
        from PySide6.QtWidgets import QApplication, QMessageBox, QDialog
    except Exception as e:
        msg = f"PySide6 import failed: {e}"
        logger.exception(msg)
        print(f"FATAL: {msg}", file=sys.stderr)
        input("Press Enter to exit...")
        return

    app = QApplication(sys.argv)
    app.setApplicationName("Screen Translator")
    app.setOrganizationName("ScreenTranslator")
    app.setStyle("Fusion")

    if study_cli or continuous_cli:
        mode = "study" if study_cli else "continuous"
        logger.info("Mode from CLI: %s", mode)
    else:
        logger.info("Showing mode selector.")
        try:
            from gui.mode_selector import ModeSelector
        except Exception as e:
            logger.exception("ModeSelector import failed, defaulting to continuous")
            _fatal_error(app, f"Launcher error: {e}\nStarting in continuous mode.")
            mode = "continuous"
        else:
            from PySide6.QtWidgets import QDialog
            selector = ModeSelector()
            result = selector.exec()
            if result != QDialog.DialogCode.Accepted or not selector.selected_mode:
                logger.info("Launcher closed without selection.")
                return
            mode = selector.selected_mode
            selector.deleteLater()
            logger.info("Mode selected: %s", mode)

    window = _create_window(mode, app)
    if window is None:
        return

    window.show()
    logger.info("Window shown. Entering event loop.")
    sys.exit(app.exec())


def _create_window(mode: str, app):
    logger = get_logger(__name__)

    if mode == "study":
        try:
            from config.settings import get_settings
            from translation import discover_translator
            from study_mode.study_window import StudyWindow
        except Exception as e:
            logger.exception("Failed to import study mode modules")
            _fatal_error(app, f"Import error: {e}\n\n{traceback.format_exc()}")
            return None

        settings = get_settings()
        try:
            translator = discover_translator(preferred=settings.active_plugin)
        except Exception:
            from translation.generic_translator import GenericTranslator
            translator = GenericTranslator()

        try:
            window = StudyWindow(settings, translator)
            logger.info("Study window created.")
            return window
        except Exception as e:
            logger.exception("Failed to create StudyWindow")
            _fatal_error(app, f"Failed to create study window:\n\n{type(e).__name__}: {e}")
            return None

    else:
        try:
            from gui.main_window import MainWindow
        except Exception as e:
            logger.exception("Failed to import MainWindow")
            _fatal_error(app, f"Import error: {e}\n\n{traceback.format_exc()}")
            return None

        try:
            window = MainWindow()
            logger.info("Main window created.")
            return window
        except Exception as e:
            logger.exception("Failed to create MainWindow")
            _fatal_error(app, f"Failed to create window:\n\n{type(e).__name__}: {e}")
            return None


def _fatal_error(app, message: str) -> None:
    try:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.critical(None, "Screen Translator - Error", message)
    except Exception:
        print(f"FATAL ERROR: {message}", file=sys.stderr)


if __name__ == "__main__":
    main()
