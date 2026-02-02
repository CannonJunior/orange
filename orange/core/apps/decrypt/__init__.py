"""
IPA Decryption Module.

This module provides functionality for decrypting FairPlay-protected iOS apps
from jailbroken devices using Frida dynamic instrumentation.

Requirements:
    - Jailbroken iOS device
    - Frida server running on device
    - SSH access to device
    - Target app installed

Example:
    from orange.core.apps.decrypt import FridaClient, AppDumper

    # Connect to device
    client = FridaClient(udid="00008030-...")
    client.connect()

    # Dump decrypted app
    dumper = AppDumper(client)
    result = dumper.dump("com.netflix.Netflix", Path("./Netflix.ipa"))
    print(f"Decrypted IPA saved to: {result.ipa_path}")
"""

from orange.core.apps.decrypt.exceptions import (
    DecryptionError,
    FridaConnectionError,
    FridaNotInstalledError,
    AppNotFoundError,
    AppNotRunningError,
    JailbreakRequiredError,
)
from orange.core.apps.decrypt.frida_client import FridaClient, FridaDeviceInfo
from orange.core.apps.decrypt.macho import MachOParser, EncryptionInfo, MachOBinary
from orange.core.apps.decrypt.dumper import AppDumper, DumpProgress, DumpResult
from orange.core.apps.decrypt.ipa_builder import IPABuilder

__all__ = [
    # Exceptions
    "DecryptionError",
    "FridaConnectionError",
    "FridaNotInstalledError",
    "AppNotFoundError",
    "AppNotRunningError",
    "JailbreakRequiredError",
    # Frida Client
    "FridaClient",
    "FridaDeviceInfo",
    # Mach-O
    "MachOParser",
    "EncryptionInfo",
    "MachOBinary",
    # Dumper
    "AppDumper",
    "DumpProgress",
    "DumpResult",
    # IPA Builder
    "IPABuilder",
]
