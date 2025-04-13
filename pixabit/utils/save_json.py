# pixabit/utils/save_file.py
import json
import os
from typing import Any, Dict, List, Union

# Import console/print if needed for messages, assuming from .display
try:
    from .display import console, print

except ImportError:  # Fallback if run standalone or display is missing
    console = None
    print = builtins.print
    import builtins


# >> ─── Save JSON ────────────────────────────────────────────────────────────────
def save_json(data: Union[Dict[str, Any], List[Any]], filepath: str) -> None:
    """
    Saves Python data (dict or list) to a JSON file with pretty printing. Ensures the output directory exists before writing. Handles potential errors.
    """
    log_func = getattr(console, "print", print)  # Use console if available

    try:
        dir_name = os.path.dirname(filepath)

        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        log_func(f"[green]Successfully saved data to:[/green] [file]{filepath}[/]")

    except TypeError as e:
        log_func(
            f"[error]Error:[/error] Data structure not JSON serializable for '{filepath}'. {e}"
        )

    except IOError as e:
        log_func(f"[error]Error:[/error] Could not write file '{filepath}': {e}")

    except Exception as e:
        log_func(
            f"[error]Error:[/error] An unexpected error occurred saving to '{filepath}': {e}"
        )
