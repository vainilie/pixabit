# pixabit/core/config.py
# -----------------------------------------------------------------------------
# Centralized Configuration Management
# -----------------------------------------------------------------------------

# SECTION: IMPORTS
from pathlib import Path
from typing import Optional

from pixabit.helpers._logger import log  # Importar logger configurado
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# SECTION: PATHS
# Use Path.cwd() or a more robust method if needed, __file__ might not work in all contexts
try:
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
except NameError:
    PROJECT_ROOT: Path = Path.cwd()  # Fallback if __file__ is not defined

DEFAULT_CACHE_DIR: Path = PROJECT_ROOT / ".pixabit_cache"
DEFAULT_DB_PATH: Path = DEFAULT_CACHE_DIR / "persistent_archive.db"
DEFAULT_TAGS_CONFIG_PATH: Path = PROJECT_ROOT / "tags.toml"  # Default location for tag factory config

# SECTION: CONFIGURATION MODELS


class HabiticaApiConfig(BaseSettings):
    """Habitica API Credentials and Base URL."""

    model_config = SettingsConfigDict(
        env_prefix="HABITICA_",  # Example: HABITICA_USER_ID
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    user_id: str = Field(..., description="Habitica User ID (UUID).")
    api_token: SecretStr = Field(..., description="Habitica API Token.")
    base_url: str = Field("https://habitica.com/api/v3/", description="Habitica API Base URL.")


class CacheConfig(BaseSettings):
    """Cache settings: paths and durations."""

    model_config = SettingsConfigDict(env_prefix="CACHE_", extra="ignore")

    base_dir: Path = Field(DEFAULT_CACHE_DIR, description="Base directory for all cache files.")
    raw_subdir: str = Field("raw", description="Subdirectory for raw API responses.")
    processed_subdir: str = Field("processed", description="Subdirectory for processed Pydantic models.")
    static_content_subdir: str = Field("static_content", description="Subdirectory for static game content.")
    archive_db_path: Path = Field(DEFAULT_DB_PATH, description="Path to the SQLite archive database.")
    default_duration_days: int = Field(7, description="Default cache duration in days for static content.")
    live_timeout_minutes: int = Field(5, description="Timeout in minutes for live data cache (user, tasks, etc.).")
    challenge_timeout_hours: int = Field(2, description="Timeout in hours for challenge list cache.")

    # Derived paths
    @property
    def raw_cache_dir(self) -> Path:
        return self.base_dir / self.raw_subdir

    @property
    def processed_cache_dir(self) -> Path:
        return self.base_dir / self.processed_subdir

    @property
    def static_content_cache_dir(self) -> Path:
        return self.base_dir / self.static_content_subdir

    @field_validator("base_dir", "archive_db_path", mode="before")
    @classmethod
    def _resolve_path(cls, v: Any) -> Path:
        return Path(v).resolve()


class TagFactoryConfig(BaseSettings):
    """Configuration for the Tag Factory (hierarchy rules)."""

    model_config = SettingsConfigDict(env_prefix="TAGS_", extra="ignore")

    config_path: Path = Field(DEFAULT_TAGS_CONFIG_PATH, description="Path to the tags.toml configuration file.")
    # Specific tag ID mappings loaded dynamically by the factory from the TOML file


# KLASS: AppConfig #! Combined Config
class AppConfig(BaseSettings):
    """Main application configuration aggregating other configs."""

    model_config = SettingsConfigDict(
        # Load settings from multiple sources if needed
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    api: HabiticaApiConfig = Field(default_factory=HabiticaApiConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    tags: TagFactoryConfig = Field(default_factory=TagFactoryConfig)  #! Assuming tags config is separate or defaults ok


# SECTION: SINGLETON INSTANCE

# Create a single, immutable instance of the configuration
try:
    app_config: AppConfig = AppConfig()

    # Ensure cache directories exist after config load
    app_config.cache.base_dir.mkdir(parents=True, exist_ok=True)
    app_config.cache.raw_cache_dir.mkdir(parents=True, exist_ok=True)
    app_config.cache.processed_cache_dir.mkdir(parents=True, exist_ok=True)
    app_config.cache.static_content_cache_dir.mkdir(parents=True, exist_ok=True)
    # Ensure parent dir for DB exists
    app_config.cache.archive_db_path.parent.mkdir(parents=True, exist_ok=True)

    log.info(f"Configuration loaded. Cache base: {app_config.cache.base_dir}")
    log.debug(f"API User ID Hint: {app_config.api.user_id[:6]}...")  # Avoid logging full ID

except ValidationError as e:
    log.critical(f"CRITICAL: Configuration validation failed:\n{e}")
    # Application might need to exit or handle this gracefully
    raise SystemExit("Configuration Error") from e
except Exception as e:
    log.critical(f"CRITICAL: Failed to initialize configuration: {e}", exc_info=True)
    raise SystemExit("Configuration Initialization Error") from e


# Export the singleton instance
__all__ = ["app_config", "AppConfig"]
