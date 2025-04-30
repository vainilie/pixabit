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

    # Configure root logger to filter messages from other modules
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        # Add a null handler to avoid "No handler found" warnings
        root_logger.addHandler(logging.NullHandler())

    # Disable propagation to root logger
    log.propagate = False

    return log


# Instancia singleton del logger (usar esta en toda la aplicación)
_log_instance = None


def get_logger():
    global _log_instance
    if _log_instance is None:
        _log_instance = setup_logging(log_level=logging.DEBUG, logger_name="Pixabit")
    return _log_instance


# Obtener la instancia del logger
log = get_logger()


# Configurar loggers de otras bibliotecas para prevenir mensajes no deseados
def configure_third_party_loggers():
    """Configura loggers de terceros para controlar su nivel de detalle"""
    # Lista de loggers de terceros que quieres silenciar o configurar
    third_party_loggers = [
        "urllib3",
        "requests",
        # Añade aquí otros módulos que generen logs no deseados
    ]

    for logger_name in third_party_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.WARNING)  # Solo muestra warnings y errores
        logger.propagate = False  # No propaga a loggers padres


# Ejecutar configuración de loggers de terceros
configure_third_party_loggers()
