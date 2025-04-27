# pixabit/config.py

from pathlib import Path

HABITICA_DATA_PATH: Path = Path("./habitica_cache")
HABITICA_DATA_RAW = "raw_content.json"
HABITICA_DATA_PROCESSED: str = "processed_content.json"
DEFAULT_CACHE_DURATION_DAYS = 7
HABITICA_DATA_PATH.mkdir(parents=True, exist_ok=True)
USER_ID = "50f36c30-60c7-46f7-92d1-be0e7c7259d6"
