import logging
import sys  # Needed for stderr console
import time
from enum import Enum
from logging import Formatter, Handler, Logger, LogRecord
from logging.handlers import RotatingFileHandler

# Import rich components
from rich.console import Console
from rich.logging import RichHandler
from rich.style import Style
from rich.text import Text

# --- Constants ---
LOG_FILENAME = "app.log"
# Format for the log file - includes timestamp, logger name, level, message
LOGFORMAT_FILE = "%(asctime)s - %(filename)s - %(lineno)d - %(levelname)s - %(message)s"
# Format for the custom console handler - just the message, as CliLogger adds prefixes
LOGFORMAT_CONSOLE = "%(message)s"
# Define a custom level for SUCCESS messages (between INFO and WARNING)
SUCCESS_LEVEL_NUM = 25

# --- Custom Log Level ---
logging.addLevelName(SUCCESS_LEVEL_NUM, "SUCCESS")


def success(self, message, *args, **kws):
    if self.isEnabledFor(SUCCESS_LEVEL_NUM):
        # Yes, logger takes its '*args' as 'args'.
        self._log(SUCCESS_LEVEL_NUM, message, args, **kws)


# Add the 'success' method to the Logger class
Logger.success = success

# --- Custom CLI Logger Components ---


class LogLevel(Enum):
    """Enum for custom log levels used by CliLogger."""

    INFO = logging.INFO
    WARN = logging.WARNING
    ERROR = logging.ERROR
    SUCCESS = SUCCESS_LEVEL_NUM
    DEBUG = logging.DEBUG  # Added for completeness


class CliLogger:
    """Handles custom formatting for console output using Rich."""

    def __init__(self, console: Console) -> None:
        self.console = console
        self.print = self.console.print  # Shortcut

    def _log(self, level: int, *messages: str) -> None:
        """Internal method to format and print log messages."""
        icon_map = {
            LogLevel.SUCCESS.value: "+ SUCCESS",
            LogLevel.INFO.value: "+ INFO",
            LogLevel.WARN.value: "- WARN",
            LogLevel.ERROR.value: "! ERROR",
            LogLevel.DEBUG.value: "d DEBUG",  # Example icon for debug
        }
        # Default icon if level not in map
        icon = icon_map.get(level, "?")

        color_map = {
            LogLevel.SUCCESS.value: "green",
            LogLevel.INFO.value: "blue",
            LogLevel.WARN.value: "yellow",
            LogLevel.ERROR.value: "red",
            LogLevel.DEBUG.value: "magenta",  # Example color for debug
        }
        # Default color
        color = color_map.get(level, "white")

        # Assemble the rich Text object
        message = Text.assemble(
            Text(f"[{icon}]", style=Style(color=color, bold=True)),
            Text(" "),  # Add a space after the icon
            # Join messages with spaces and apply color
            # Text(" ".join(messages), style=color),
            # Alternative if you want markup in messages:
            *[Text.from_markup(f" {msg}", style=color) for msg in messages],
        )
        self.print(message)

    # Methods corresponding to standard logging levels + success
    def info(self, *messages: str) -> None:
        self._log(LogLevel.INFO.value, *messages)

    def warn(self, *messages: str) -> None:
        self._log(LogLevel.WARN.value, *messages)

    def error(self, *messages: str) -> None:
        self._log(LogLevel.ERROR.value, *messages)

    def success(self, *messages: str) -> None:
        self._log(LogLevel.SUCCESS.value, *messages)

    def debug(self, *messages: str) -> None:
        self._log(LogLevel.DEBUG.value, *messages)


class CliLoggerHandler(Handler):
    """Custom logging handler that routes log messages to CliLogger."""

    def __init__(self, cli_logger: CliLogger, level: int | str = logging.NOTSET) -> None:
        super().__init__(level=level)
        self.cli_logger = cli_logger

    def emit(self, record: LogRecord) -> None:
        """Formats the record and passes the message to the appropriate CliLogger method."""
        try:
            log_message = self.format(record)  # Get the core message string
            level = record.levelno

            if level == LogLevel.SUCCESS.value:
                self.cli_logger.success(log_message)
            elif level == LogLevel.ERROR.value:
                # Pass exception info if available for potential future handling
                # though CliLogger currently doesn't use it.
                self.cli_logger.error(log_message)
                if record.exc_info:
                    # Optionally print rich traceback separately if needed
                    # This handler focuses on the CliLogger format.
                    pass
            elif level == LogLevel.WARN.value:
                self.cli_logger.warn(log_message)
            elif level == LogLevel.INFO.value:
                self.cli_logger.info(log_message)
            elif level == LogLevel.DEBUG.value:
                self.cli_logger.debug(log_message)
            else:
                # Handle any other levels (like CRITICAL) generically if needed
                self.cli_logger.info(f"[{record.levelname}] {log_message}")

        except Exception:
            self.handleError(record)


# --- Logging Setup Function ---
def setup_logging(log_level: int = logging.DEBUG, logger_name: str = "Yunn") -> logging.Logger:
    """Configures logging with file and custom console handlers."""
    # Get the logger
    log = logging.getLogger(logger_name)
    log.setLevel(log_level)  # Set the minimum level the logger will handle

    # Prevent adding handlers multiple times if this function is called again
    if log.hasHandlers():
        log.handlers.clear()

    # --- Create Consoles ---
    # Console for standard output (used by CliLogger)
    stdout_console = Console(stderr=False)
    # Console for error output (potentially for RichHandler tracebacks)
    stderr_console = Console(stderr=True)

    # --- Create Custom Console Handler ---
    cli_logger_instance = CliLogger(console=stdout_console)
    cli_handler = CliLoggerHandler(cli_logger_instance)
    cli_handler.setLevel(logging.INFO)  # Only show INFO and above on console via this handler
    cli_handler.setFormatter(Formatter(LOGFORMAT_CONSOLE))
    log.addHandler(cli_handler)

    # --- Create File Handler ---
    # Use RotatingFileHandler for better log management
    file_handler = RotatingFileHandler(
        LOG_FILENAME, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)  # Log everything to the file
    file_handler.setFormatter(Formatter(LOGFORMAT_FILE))
    log.addHandler(file_handler)

    # --- Optional: Add RichHandler for Tracebacks ---
    # This handler will specifically format exceptions nicely to stderr.
    # It's set to WARNING level so it doesn't duplicate INFO messages from CliLoggerHandler.
    rich_traceback_handler = RichHandler(
        level=logging.WARNING,  # Only handle WARNING and above
        console=stderr_console,
        rich_tracebacks=True,
        show_path=False,  # Don't show path, level, time as CliLogger handles basic info
        show_level=False,
        show_time=False,
        markup=True,  # Enable markup for better formatting if needed
    )
    # Use a simple formatter for this handler, as we only care about the message/traceback
    rich_traceback_handler.setFormatter(Formatter(LOGFORMAT_CONSOLE))
    log.addHandler(rich_traceback_handler)

    # --- BasicConfig (Optional - Alternative Root Logger Setup) ---
    # Instead of configuring a specific logger ('Yunn'), you could configure the root logger.
    # Generally, configuring a specific logger (as done above) is more flexible.
    # Avoid calling basicConfig if you configure loggers directly like above.
    # If you *did* want to use basicConfig (call ONLY ONCE at startup):
    # logging.basicConfig(
    #   level=log_level,
    #   format=LOGFORMAT_FILE, # Default format (applied if handler has no formatter)
    #   handlers=[file_handler, cli_handler, rich_traceback_handler]
    # )
    # log = logging.getLogger(logger_name) # Still get named logger after basicConfig

    return log


log = setup_logging(log_level=logging.DEBUG, logger_name="MyApp")
# --- Example Usage ---
# Setup logging - you only need to do this once in your application entry point
