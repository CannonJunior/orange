"""
iOS App Manager for listing and extracting applications.

This module provides functionality for:
- Listing installed iOS applications
- Extracting IPA files from devices
- Querying app metadata
"""

from __future__ import annotations

import logging
import tempfile
import zipfile
import shutil
from pathlib import Path
from typing import Optional, Callable, Any

from pymobiledevice3.services.installation_proxy import InstallationProxyService
from pymobiledevice3.services.afc import AfcService
from pymobiledevice3.services.house_arrest import HouseArrestService

from orange.core.connection import create_lockdown_client
from orange.core.apps.models import AppInfo, AppType
from orange.exceptions import DeviceNotFoundError, OrangeError

logger = logging.getLogger(__name__)


class AppExtractionError(OrangeError):
    """Error during app extraction."""

    pass


class AppManager:
    """
    Manages iOS applications on connected devices.

    Provides functionality for listing installed apps, querying
    app metadata, and extracting IPA files.

    Example:
        manager = AppManager("device-udid")

        # List all user apps
        apps = manager.list_apps(app_type=AppType.USER)
        for app in apps:
            print(f"{app.name}: {app.size_human}")

        # Extract Netflix IPA
        manager.extract_ipa(
            "com.netflix.Netflix",
            Path("./Netflix.ipa")
        )
    """

    def __init__(self, udid: Optional[str] = None):
        """
        Initialize app manager.

        Args:
            udid: Device UDID. If None, uses first connected device.
        """
        self._udid = udid
        self._lockdown = None
        self._installation_proxy = None

        logger.debug(f"AppManager initialized for {udid or 'first device'}")

    def _ensure_connected(self) -> InstallationProxyService:
        """Ensure connection to installation proxy service."""
        if self._installation_proxy is None:
            try:
                self._lockdown = create_lockdown_client(self._udid)
                self._installation_proxy = InstallationProxyService(
                    lockdown=self._lockdown
                )
                logger.debug("Installation proxy connection established")
            except Exception as e:
                raise DeviceNotFoundError(self._udid or "unknown") from e

        return self._installation_proxy

    def close(self) -> None:
        """Close connections."""
        if self._installation_proxy:
            try:
                self._installation_proxy.close()
            except Exception:
                pass
            self._installation_proxy = None
            self._lockdown = None

    def __enter__(self) -> "AppManager":
        """Context manager entry."""
        self._ensure_connected()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()

    def list_apps(
        self,
        app_type: AppType = AppType.USER,
        calculate_sizes: bool = True,
        bundle_ids: Optional[list[str]] = None,
    ) -> list[AppInfo]:
        """
        List installed applications.

        Args:
            app_type: Type of apps to list (USER, SYSTEM, ANY)
            calculate_sizes: Whether to calculate app sizes (slower)
            bundle_ids: Optional list of specific bundle IDs to query

        Returns:
            List of AppInfo objects for installed apps.
        """
        proxy = self._ensure_connected()

        try:
            apps_dict = proxy.get_apps(
                application_type=app_type.value,
                calculate_sizes=calculate_sizes,
                bundle_identifiers=bundle_ids,
            )

            apps = []
            for bundle_id, info in apps_dict.items():
                app_info = self._parse_app_info(bundle_id, info)
                apps.append(app_info)

            # Sort by name
            apps.sort(key=lambda a: a.name.lower())

            logger.info(f"Found {len(apps)} {app_type.value.lower()} app(s)")
            return apps

        except Exception as e:
            logger.error(f"Failed to list apps: {e}")
            raise

    def get_app(self, bundle_id: str) -> Optional[AppInfo]:
        """
        Get information for a specific app.

        Args:
            bundle_id: The app's bundle identifier.

        Returns:
            AppInfo if found, None otherwise.
        """
        apps = self.list_apps(
            app_type=AppType.ANY,
            calculate_sizes=True,
            bundle_ids=[bundle_id],
        )
        return apps[0] if apps else None

    def search_apps(self, query: str) -> list[AppInfo]:
        """
        Search for apps by name or bundle ID.

        Args:
            query: Search query (case-insensitive)

        Returns:
            List of matching AppInfo objects.
        """
        all_apps = self.list_apps(app_type=AppType.USER, calculate_sizes=False)
        query_lower = query.lower()

        return [
            app
            for app in all_apps
            if query_lower in app.name.lower()
            or query_lower in app.bundle_id.lower()
        ]

    def extract_ipa(
        self,
        bundle_id: str,
        output_path: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> Path:
        """
        Extract an IPA file from the device.

        NOTE: The extracted IPA will be FairPlay encrypted if it was
        downloaded from the App Store. Decryption requires a jailbroken
        device and tools like frida-ios-dump.

        Args:
            bundle_id: Bundle identifier of the app to extract.
            output_path: Path to save the IPA file.
            progress_callback: Optional callback(bytes_done, total_bytes)

        Returns:
            Path to the extracted IPA file.

        Raises:
            AppExtractionError: If extraction fails.
        """
        # Get app info first
        app_info = self.get_app(bundle_id)
        if not app_info:
            raise AppExtractionError(f"App not found: {bundle_id}")

        if not app_info.is_extractable:
            raise AppExtractionError(
                f"Cannot extract system app: {bundle_id}"
            )

        if not app_info.path:
            raise AppExtractionError(
                f"App path not available: {bundle_id}"
            )

        logger.info(f"Extracting {app_info.name} ({bundle_id})...")

        try:
            # Create lockdown client for AFC
            lockdown = create_lockdown_client(self._udid)

            # Use HouseArrest to access app container
            with HouseArrestService(lockdown=lockdown, bundle_id=bundle_id) as ha:
                afc = ha.send_command("VendContainer")

                # Create temporary directory for extraction
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    app_dir = temp_path / "Payload"
                    app_dir.mkdir()

                    # Extract app bundle
                    bundle_name = Path(app_info.path).name
                    local_app_path = app_dir / bundle_name

                    logger.debug(f"Downloading app bundle to {local_app_path}")
                    self._download_directory(
                        afc,
                        "/",
                        local_app_path,
                        progress_callback,
                    )

                    # Create IPA (zip file)
                    output_path = Path(output_path)
                    if output_path.suffix.lower() != ".ipa":
                        output_path = output_path.with_suffix(".ipa")

                    output_path.parent.mkdir(parents=True, exist_ok=True)

                    logger.debug(f"Creating IPA at {output_path}")
                    with zipfile.ZipFile(
                        output_path, "w", zipfile.ZIP_DEFLATED
                    ) as zf:
                        for file_path in temp_path.rglob("*"):
                            if file_path.is_file():
                                arc_name = file_path.relative_to(temp_path)
                                zf.write(file_path, arc_name)

            logger.info(f"Extracted IPA to {output_path}")

            # Warn about encryption
            logger.warning(
                "NOTE: This IPA is likely FairPlay encrypted. "
                "To use with PlayCover, you need a decrypted IPA. "
                "See docs/playcover-integration.md for details."
            )

            return output_path

        except Exception as e:
            logger.error(f"Failed to extract IPA: {e}")
            raise AppExtractionError(f"Extraction failed: {e}") from e

    def _download_directory(
        self,
        afc: Any,
        remote_path: str,
        local_path: Path,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """Recursively download a directory from device."""
        local_path.mkdir(parents=True, exist_ok=True)

        try:
            items = afc.listdir(remote_path)
        except Exception:
            return

        for item in items:
            if item in (".", ".."):
                continue

            remote_item = f"{remote_path.rstrip('/')}/{item}"
            local_item = local_path / item

            try:
                # Check if directory
                if afc.isdir(remote_item):
                    self._download_directory(
                        afc, remote_item, local_item, progress_callback
                    )
                else:
                    # Download file
                    afc.pull(remote_item, str(local_item))
                    if progress_callback:
                        try:
                            stat = afc.stat(remote_item)
                            size = int(stat.get("st_size", 0))
                            progress_callback(size, size)
                        except Exception:
                            pass
            except Exception as e:
                logger.debug(f"Could not download {remote_item}: {e}")

    def _parse_app_info(self, bundle_id: str, info: dict) -> AppInfo:
        """Parse app info dictionary into AppInfo object."""
        # Determine app type
        app_type_str = info.get("ApplicationType", "User")
        try:
            app_type = AppType(app_type_str)
        except ValueError:
            app_type = AppType.USER

        # Check if sideloaded (no App Store receipt)
        is_sideloaded = not info.get("iTunesMetadata")

        # Get icon files
        icon_files = []
        icons = info.get("CFBundleIcons", {})
        primary = icons.get("CFBundlePrimaryIcon", {})
        icon_files = primary.get("CFBundleIconFiles", [])

        return AppInfo(
            bundle_id=bundle_id,
            name=info.get("CFBundleDisplayName")
            or info.get("CFBundleName", bundle_id),
            version=info.get("CFBundleVersion", "Unknown"),
            short_version=info.get("CFBundleShortVersionString", "Unknown"),
            app_type=app_type,
            path=info.get("Path"),
            container_path=info.get("Container"),
            size=info.get("StaticDiskUsage", 0),
            data_size=info.get("DynamicDiskUsage", 0),
            is_sideloaded=is_sideloaded,
            min_os_version=info.get("MinimumOSVersion"),
            executable_name=info.get("CFBundleExecutable"),
            icon_files=icon_files,
            entitlements=info.get("Entitlements", {}),
            extra={
                "signer_identity": info.get("SignerIdentity"),
                "team_id": info.get("TeamIdentifier"),
                "app_store_receipt": bool(info.get("iTunesMetadata")),
            },
        )
