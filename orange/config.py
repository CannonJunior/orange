"""
Configuration management for Orange.

Handles loading, saving, and accessing configuration values from
environment variables, config files, and default values.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

from orange.constants import (
    DEFAULT_BACKUP_DIR,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CONFIG_DIR,
    DEFAULT_CONFIG_FILE,
    DEFAULT_CONNECTION_TIMEOUT,
    DEFAULT_EXPORT_DIR,
    DEFAULT_LOG_DIR,
    DEFAULT_PAIRING_TIMEOUT,
    MAX_CONCURRENT_TRANSFERS,
    AUDIO_FORMAT_ALAC,
    VIDEO_FORMAT_MP4,
    IMAGE_FORMAT_JPEG,
)

logger = logging.getLogger(__name__)


@dataclass
class ConnectionConfig:
    """Configuration for device connections."""

    timeout: int = DEFAULT_CONNECTION_TIMEOUT
    pairing_timeout: int = DEFAULT_PAIRING_TIMEOUT
    wifi_discovery_enabled: bool = True
    auto_reconnect: bool = True
    max_reconnect_attempts: int = 3


@dataclass
class TransferConfig:
    """Configuration for file transfers."""

    chunk_size: int = DEFAULT_CHUNK_SIZE
    max_concurrent: int = MAX_CONCURRENT_TRANSFERS
    verify_checksums: bool = True
    resume_interrupted: bool = True


@dataclass
class ConversionConfig:
    """Configuration for media conversion."""

    audio_format: str = AUDIO_FORMAT_ALAC
    video_format: str = VIDEO_FORMAT_MP4
    image_format: str = IMAGE_FORMAT_JPEG
    preserve_metadata: bool = True
    quality: int = 90  # For lossy formats


@dataclass
class ExportConfig:
    """Configuration for data export."""

    pdf_include_attachments: bool = True
    pdf_page_size: str = "letter"
    csv_delimiter: str = ","
    csv_quote_all: bool = False
    json_indent: int = 2
    json_ensure_ascii: bool = False


@dataclass
class Config:
    """
    Main configuration container for Orange.

    Configuration is loaded from (in order of precedence):
    1. Environment variables (ORANGE_*)
    2. Config file (~/.orange/config.json)
    3. Default values

    Example:
        config = Config.load()
        print(config.paths.backup_dir)

        # Or with custom config file
        config = Config.load(Path("/custom/config.json"))
    """

    # Directory paths
    config_dir: Path = field(default_factory=lambda: DEFAULT_CONFIG_DIR)
    backup_dir: Path = field(default_factory=lambda: DEFAULT_BACKUP_DIR)
    export_dir: Path = field(default_factory=lambda: DEFAULT_EXPORT_DIR)
    log_dir: Path = field(default_factory=lambda: DEFAULT_LOG_DIR)

    # Sub-configurations
    connection: ConnectionConfig = field(default_factory=ConnectionConfig)
    transfer: TransferConfig = field(default_factory=TransferConfig)
    conversion: ConversionConfig = field(default_factory=ConversionConfig)
    export: ExportConfig = field(default_factory=ExportConfig)

    # Logging
    log_level: str = "INFO"
    log_to_file: bool = False

    def __post_init__(self) -> None:
        """Ensure paths are Path objects."""
        self.config_dir = Path(self.config_dir)
        self.backup_dir = Path(self.backup_dir)
        self.export_dir = Path(self.export_dir)
        self.log_dir = Path(self.log_dir)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> Config:
        """
        Load configuration from file and environment.

        Args:
            config_path: Optional path to config file. If not provided,
                        uses default location (~/.orange/config.json).

        Returns:
            Config instance with loaded values.
        """
        # Load environment variables from .env file if present
        load_dotenv()

        config_path = config_path or DEFAULT_CONFIG_FILE
        config_data: dict[str, Any] = {}

        # Load from file if it exists
        if config_path.exists():
            try:
                with open(config_path) as f:
                    config_data = json.load(f)
                logger.debug(f"Loaded config from {config_path}")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load config from {config_path}: {e}")

        # Apply environment variable overrides
        config_data = cls._apply_env_overrides(config_data)

        # Build config object
        return cls._from_dict(config_data)

    @classmethod
    def _apply_env_overrides(cls, config_data: dict[str, Any]) -> dict[str, Any]:
        """Apply environment variable overrides to config data."""
        env_mappings = {
            "ORANGE_CONFIG_DIR": "config_dir",
            "ORANGE_BACKUP_DIR": "backup_dir",
            "ORANGE_EXPORT_DIR": "export_dir",
            "ORANGE_LOG_DIR": "log_dir",
            "ORANGE_LOG_LEVEL": "log_level",
            "ORANGE_CONNECTION_TIMEOUT": ("connection", "timeout"),
            "ORANGE_PAIRING_TIMEOUT": ("connection", "pairing_timeout"),
            "ORANGE_WIFI_DISCOVERY": ("connection", "wifi_discovery_enabled"),
            "ORANGE_CHUNK_SIZE": ("transfer", "chunk_size"),
        }

        for env_var, config_key in env_mappings.items():
            value = os.environ.get(env_var)
            if value is not None:
                if isinstance(config_key, tuple):
                    # Nested config
                    section, key = config_key
                    if section not in config_data:
                        config_data[section] = {}
                    config_data[section][key] = cls._parse_env_value(value)
                else:
                    config_data[config_key] = cls._parse_env_value(value)

        return config_data

    @staticmethod
    def _parse_env_value(value: str) -> Any:
        """Parse environment variable value to appropriate type."""
        # Boolean
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False

        # Integer
        try:
            return int(value)
        except ValueError:
            pass

        # Float
        try:
            return float(value)
        except ValueError:
            pass

        # String
        return value

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> Config:
        """Create Config from dictionary."""
        # Handle nested configs
        connection_data = data.pop("connection", {})
        transfer_data = data.pop("transfer", {})
        conversion_data = data.pop("conversion", {})
        export_data = data.pop("export", {})

        return cls(
            config_dir=Path(data.get("config_dir", DEFAULT_CONFIG_DIR)),
            backup_dir=Path(data.get("backup_dir", DEFAULT_BACKUP_DIR)),
            export_dir=Path(data.get("export_dir", DEFAULT_EXPORT_DIR)),
            log_dir=Path(data.get("log_dir", DEFAULT_LOG_DIR)),
            connection=ConnectionConfig(**connection_data),
            transfer=TransferConfig(**transfer_data),
            conversion=ConversionConfig(**conversion_data),
            export=ExportConfig(**export_data),
            log_level=data.get("log_level", "INFO"),
            log_to_file=data.get("log_to_file", False),
        )

    def save(self, config_path: Optional[Path] = None) -> None:
        """
        Save configuration to file.

        Args:
            config_path: Optional path to save to. If not provided,
                        uses default location.
        """
        config_path = config_path or DEFAULT_CONFIG_FILE

        # Ensure directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict for serialization
        data = self.to_dict()

        with open(config_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"Saved config to {config_path}")

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "config_dir": str(self.config_dir),
            "backup_dir": str(self.backup_dir),
            "export_dir": str(self.export_dir),
            "log_dir": str(self.log_dir),
            "connection": asdict(self.connection),
            "transfer": asdict(self.transfer),
            "conversion": asdict(self.conversion),
            "export": asdict(self.export),
            "log_level": self.log_level,
            "log_to_file": self.log_to_file,
        }

    def ensure_directories(self) -> None:
        """Create all configured directories if they don't exist."""
        for directory in [
            self.config_dir,
            self.backup_dir,
            self.export_dir,
            self.log_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)


# Global config instance (lazy loaded)
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def reload_config(config_path: Optional[Path] = None) -> Config:
    """Reload configuration from file."""
    global _config
    _config = Config.load(config_path)
    return _config
