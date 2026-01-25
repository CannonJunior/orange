"""
Constants used throughout the Orange package.

This module contains all magic numbers, default values, and constant
strings used by various components. Import from here rather than
hardcoding values elsewhere.
"""

from pathlib import Path

# Version info
VERSION = "0.1.0"
APP_NAME = "Orange"

# Default paths
DEFAULT_CONFIG_DIR = Path.home() / ".orange"
DEFAULT_BACKUP_DIR = DEFAULT_CONFIG_DIR / "backups"
DEFAULT_EXPORT_DIR = DEFAULT_CONFIG_DIR / "exports"
DEFAULT_LOG_DIR = DEFAULT_CONFIG_DIR / "logs"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"

# Connection settings
DEFAULT_CONNECTION_TIMEOUT = 30  # seconds
DEFAULT_PAIRING_TIMEOUT = 60  # seconds
DEFAULT_SERVICE_TIMEOUT = 10  # seconds
MAX_RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY = 2  # seconds

# Transfer settings
DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MB
MAX_CONCURRENT_TRANSFERS = 4

# Wi-Fi discovery
WIFI_DISCOVERY_TIMEOUT = 5  # seconds
BONJOUR_SERVICE_TYPE = "_apple-mobdev2._tcp.local."

# iOS service names
SERVICE_AFC = "com.apple.afc"
SERVICE_AFC2 = "com.apple.afc2"
SERVICE_BACKUP = "com.apple.mobilebackup2"
SERVICE_INSTALLATION_PROXY = "com.apple.mobile.installation_proxy"
SERVICE_NOTIFICATION_PROXY = "com.apple.mobile.notification_proxy"
SERVICE_SPRINGBOARD = "com.apple.springboardservices"
SERVICE_SCREENSHOT = "com.apple.screenshotr"
SERVICE_SYSLOG = "com.apple.syslog_relay"
SERVICE_CRASHREPORT = "com.apple.crashreportcopymobile"
SERVICE_HOUSE_ARREST = "com.apple.mobile.house_arrest"

# Device information keys
DEVICE_INFO_KEYS = [
    "DeviceName",
    "DeviceClass",
    "ProductType",
    "ProductVersion",
    "BuildVersion",
    "SerialNumber",
    "UniqueDeviceID",
    "WiFiAddress",
    "BluetoothAddress",
    "PhoneNumber",
    "ModelNumber",
    "RegionInfo",
    "TimeZone",
    "HardwareModel",
    "ActivationState",
    "BatteryCurrentCapacity",
    "BatteryIsCharging",
]

# Battery level thresholds
BATTERY_LOW = 20
BATTERY_CRITICAL = 10

# Export formats
EXPORT_FORMAT_PDF = "pdf"
EXPORT_FORMAT_CSV = "csv"
EXPORT_FORMAT_JSON = "json"
EXPORT_FORMAT_HTML = "html"
EXPORT_FORMAT_TXT = "txt"
EXPORT_FORMAT_VCF = "vcf"  # vCard for contacts
EXPORT_FORMAT_ICS = "ics"  # iCalendar

SUPPORTED_EXPORT_FORMATS = [
    EXPORT_FORMAT_PDF,
    EXPORT_FORMAT_CSV,
    EXPORT_FORMAT_JSON,
    EXPORT_FORMAT_HTML,
    EXPORT_FORMAT_TXT,
]

# Audio formats
AUDIO_FORMAT_ALAC = "alac"
AUDIO_FORMAT_AAC = "aac"
AUDIO_FORMAT_MP3 = "mp3"
AUDIO_FORMAT_FLAC = "flac"
AUDIO_FORMAT_WAV = "wav"

# Image formats
IMAGE_FORMAT_HEIC = "heic"
IMAGE_FORMAT_JPEG = "jpeg"
IMAGE_FORMAT_PNG = "png"

# Video formats
VIDEO_FORMAT_MP4 = "mp4"
VIDEO_FORMAT_MOV = "mov"
VIDEO_FORMAT_MKV = "mkv"
VIDEO_FORMAT_AVI = "avi"

# Apple epoch offset (seconds between Unix epoch and Apple epoch)
# Apple epoch is January 1, 2001; Unix epoch is January 1, 1970
APPLE_EPOCH_OFFSET = 978307200

# Message database date divisor (iOS uses nanoseconds in newer versions)
MESSAGE_DATE_DIVISOR = 1_000_000_000
