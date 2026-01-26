"""
File transfer module for Orange.

This module provides functionality for browsing device files and
transferring files between iOS devices and computers.

Example:
    from orange.core.transfer import FileManager, DeviceBrowser

    # Browse device files
    browser = DeviceBrowser(udid)
    for item in browser.list_directory("/DCIM"):
        print(f"{item.name} - {item.size}")

    # Transfer files
    manager = FileManager(udid)
    manager.pull("/DCIM/100APPLE", "./photos/")
"""

from orange.core.transfer.browser import DeviceBrowser, FileInfo
from orange.core.transfer.manager import FileManager
from orange.core.transfer.categories import (
    DataCategory,
    CATEGORIES,
    get_category,
    list_categories,
)

__all__ = [
    "DataCategory",
    "DeviceBrowser",
    "FileInfo",
    "FileManager",
    "CATEGORIES",
    "get_category",
    "list_categories",
]
