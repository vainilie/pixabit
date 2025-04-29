import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from textual.logging import TextualHandler

# --- Constants ---
LOG_FILENAME = "app.log"
LOG_FORMAT_FILE = "%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s"
SUCCESS_LEVEL_NUM = 25

# --- Custom Success Level ---
logging.addLevelName(SUCCESS_LEVEL_NUM, "SUCCESS")


def success(self, message, *args, **kws):
    if self.isEnabledFor(SUCCESS_LEVEL_NUM):
        self._log(SUCCESS_LEVEL_NUM, message, args, **kws)


logging.Logger.success = success


def setup_logging(
    log_level: int = logging.DEBUG,
    logger_name: str = "Pixabit",
    log_dir: Path = None,
) -> logging.Logger:
    """Configura logging con TextualHandler para la consola de Textual"""
    # Crear directorio de logs si es necesario
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / LOG_FILENAME
    else:
        log_path = LOG_FILENAME

    # Get the logger
    log = logging.getLogger(logger_name)
    log.setLevel(log_level)

    # Clear existing handlers to prevent duplicates
    if log.hasHandlers():
        log.handlers.clear()

    # Usar TextualHandler para la consola de Textual
    textual_handler = TextualHandler()
    textual_handler.setLevel(logging.WARNING)
    log.addHandler(textual_handler)

    # File handler para logs en archivo
    file_handler = RotatingFileHandler(log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(LOG_FORMAT_FILE)
    file_handler.setFormatter(file_formatter)
    log.addHandler(file_handler)

    # # Add custom level names to Rich formats
    # logging._levelToName[SUCCESS_LEVEL_NUM] = "SUCCESS"

    # # Forward Textual logs to our handler
    # try:
    #     textual_logger = logging.getLogger("textual")
    #     textual_logger.setLevel(log_level)
    #     textual_logger.handlers.clear()
    #     textual_logger.addHandler(rich_handler)
    # except Exception:
    #     pass

    return log


# Instancia singleton del logger
_log_instance = None


def get_logger():
    global _log_instance
    if _log_instance is None:
        _log_instance = setup_logging(log_level=logging.INFO, logger_name="Pixabit")
    return _log_instance


# Crear instancia del logger
log = setup_logging(log_level=logging.DEBUG, logger_name="Pixabit")
# # --- Singleton Access ---


# def get_logger() -> Logger:
#     global _log_instance
#     if _log_instance is None:
#         _log_instance = setup_logging(log_level=logging.INFO, logger_name="Pixabit")
#     return _log_instance


# Example usage in a Textual app:
# from textual.app import App
#
# class MyApp(App):
#     def on_mount(self):
#         log.info("Application started")
#         log.success("Setup complete!")
#
#     def on_error(self, event):
#         log.error(f"Error occurred: {event.error}")
