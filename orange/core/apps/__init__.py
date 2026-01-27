"""
iOS App Management Module.

This module provides functionality for listing installed iOS apps,
extracting IPA files, and managing app data.

Example:
    from orange.core.apps import AppManager, AppInfo

    # List installed apps
    manager = AppManager(udid)
    apps = manager.list_apps()
    for app in apps:
        print(f"{app.name} ({app.bundle_id})")

    # Extract an IPA
    manager.extract_ipa("com.netflix.Netflix", "/path/to/output.ipa")
"""

from orange.core.apps.models import AppInfo, AppType
from orange.core.apps.manager import AppManager

__all__ = [
    "AppInfo",
    "AppManager",
    "AppType",
]
