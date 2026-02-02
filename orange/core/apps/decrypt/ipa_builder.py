"""
IPA builder for reconstructing decrypted iOS applications.

This module handles creating properly formatted IPA files
from app bundles with decrypted binaries.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from orange.core.apps.decrypt.macho import MachOParser
from orange.core.apps.decrypt.exceptions import DecryptionError

if TYPE_CHECKING:
    from orange.core.apps.decrypt.dumper import BinaryDumpInfo

logger = logging.getLogger(__name__)


class IPABuilder:
    """
    Builds IPA files from app bundles with decrypted binaries.

    An IPA file is a ZIP archive with the following structure:
        Payload/
            AppName.app/
                (app contents)
        iTunesMetadata.plist (optional)
        iTunesArtwork (optional)

    Example:
        builder = IPABuilder()
        ipa_path = builder.build(
            app_bundle_path=Path("/tmp/Netflix.app"),
            output_path=Path("./Netflix-decrypted.ipa"),
            main_binary_dump=dump_info,
        )
    """

    def __init__(self, work_dir: Optional[Path] = None):
        """
        Initialize IPA builder.

        Args:
            work_dir: Working directory for assembly.
                     If None, uses system temp directory.
        """
        self.work_dir = work_dir

    def build(
        self,
        app_bundle_path: Path,
        output_path: Path,
        main_binary_dump: "BinaryDumpInfo",
        framework_dumps: Optional[list["BinaryDumpInfo"]] = None,
    ) -> Path:
        """
        Build an IPA from an app bundle with decrypted binaries.

        Args:
            app_bundle_path: Path to the .app bundle directory.
            output_path: Where to save the IPA file.
            main_binary_dump: Dump info for main executable.
            framework_dumps: Optional list of framework dump infos.

        Returns:
            Path to the created IPA file.

        Raises:
            DecryptionError: If build fails.
        """
        if not app_bundle_path.exists():
            raise DecryptionError(f"App bundle not found: {app_bundle_path}")

        # Create working directory
        if self.work_dir:
            work_dir = self.work_dir
            work_dir.mkdir(parents=True, exist_ok=True)
        else:
            work_dir = Path(tempfile.mkdtemp(prefix="orange_ipa_"))

        try:
            # Create Payload structure
            payload_dir = work_dir / "Payload"
            payload_dir.mkdir(exist_ok=True)

            # Copy app bundle to Payload
            app_name = app_bundle_path.name
            dest_app_path = payload_dir / app_name
            logger.debug(f"Copying app bundle to {dest_app_path}")
            shutil.copytree(app_bundle_path, dest_app_path, symlinks=True)

            # Replace main binary with decrypted version
            if main_binary_dump.decrypted_section and main_binary_dump.encryption_info:
                self._replace_binary(
                    dest_app_path,
                    main_binary_dump,
                )

            # Replace framework binaries if provided
            if framework_dumps:
                for fw_dump in framework_dumps:
                    if fw_dump.decrypted_section and fw_dump.encryption_info:
                        self._replace_framework_binary(dest_app_path, fw_dump)

            # Create IPA (ZIP file)
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Remove existing file if present
            if output_path.exists():
                output_path.unlink()

            logger.debug(f"Creating IPA: {output_path}")
            self._create_ipa(payload_dir, output_path)

            return output_path

        finally:
            # Clean up temp directory if we created it
            if not self.work_dir:
                shutil.rmtree(work_dir, ignore_errors=True)

    def _replace_binary(
        self,
        app_path: Path,
        dump_info: "BinaryDumpInfo",
    ) -> None:
        """
        Replace the main binary with a decrypted version.

        Args:
            app_path: Path to the .app directory.
            dump_info: Binary dump information.
        """
        # Find the main executable
        # Read CFBundleExecutable from Info.plist
        info_plist = app_path / "Info.plist"
        executable_name = self._get_executable_name(info_plist)

        if not executable_name:
            # Fallback to dump info
            executable_name = dump_info.name

        binary_path = app_path / executable_name

        if not binary_path.exists():
            # Try common locations
            for candidate in [
                app_path / executable_name,
                app_path / dump_info.name,
            ]:
                if candidate.exists():
                    binary_path = candidate
                    break
            else:
                raise DecryptionError(
                    f"Could not find main executable in {app_path}"
                )

        logger.debug(f"Replacing binary: {binary_path}")

        # Read original binary
        original_data = binary_path.read_bytes()

        # Create decrypted binary
        decrypted_data = MachOParser.patch_binary_cryptid(
            binary_data=original_data,
            decrypted_section=dump_info.decrypted_section,
            encryption_info=dump_info.encryption_info,
        )

        # Write decrypted binary
        binary_path.write_bytes(decrypted_data)
        logger.debug(f"Wrote decrypted binary: {len(decrypted_data)} bytes")

    def _replace_framework_binary(
        self,
        app_path: Path,
        dump_info: "BinaryDumpInfo",
    ) -> None:
        """
        Replace a framework binary with a decrypted version.

        Args:
            app_path: Path to the .app directory.
            dump_info: Framework dump information.
        """
        # Extract framework name from path
        # e.g., /path/to/App.app/Frameworks/SomeFramework.framework/SomeFramework
        framework_name = dump_info.name

        # Find the framework in the app bundle
        frameworks_dir = app_path / "Frameworks"
        if not frameworks_dir.exists():
            logger.warning(f"Frameworks directory not found: {frameworks_dir}")
            return

        # Look for matching framework
        for framework_path in frameworks_dir.glob("*.framework"):
            binary_path = framework_path / framework_name
            if binary_path.exists():
                logger.debug(f"Replacing framework binary: {binary_path}")

                original_data = binary_path.read_bytes()

                decrypted_data = MachOParser.patch_binary_cryptid(
                    binary_data=original_data,
                    decrypted_section=dump_info.decrypted_section,
                    encryption_info=dump_info.encryption_info,
                )

                binary_path.write_bytes(decrypted_data)
                return

        logger.warning(f"Framework binary not found: {framework_name}")

    def _get_executable_name(self, info_plist: Path) -> Optional[str]:
        """
        Extract CFBundleExecutable from Info.plist.

        Args:
            info_plist: Path to Info.plist file.

        Returns:
            Executable name or None if not found.
        """
        if not info_plist.exists():
            return None

        try:
            import plistlib

            with open(info_plist, "rb") as f:
                plist = plistlib.load(f)
            return plist.get("CFBundleExecutable")
        except Exception as e:
            logger.debug(f"Failed to read Info.plist: {e}")
            return None

    def _create_ipa(self, payload_dir: Path, output_path: Path) -> None:
        """
        Create IPA file from Payload directory.

        Args:
            payload_dir: Path to Payload directory.
            output_path: Output IPA path.
        """
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Walk the Payload directory
            for file_path in payload_dir.rglob("*"):
                if file_path.is_file():
                    # Calculate archive name (relative to parent of Payload)
                    arcname = file_path.relative_to(payload_dir.parent)
                    zf.write(file_path, arcname)
                elif file_path.is_symlink():
                    # Handle symlinks
                    arcname = file_path.relative_to(payload_dir.parent)
                    # Create a ZipInfo for the symlink
                    info = zipfile.ZipInfo(str(arcname))
                    info.external_attr = 0xA1ED0000  # Symlink
                    zf.writestr(info, str(file_path.readlink()))

        logger.info(f"Created IPA: {output_path}")


def build_ipa_simple(
    app_bundle: Path,
    output_path: Path,
    decrypted_binary: bytes,
    executable_name: str,
) -> Path:
    """
    Simplified IPA builder for basic use cases.

    This function provides a simpler interface when you already
    have the decrypted binary data.

    Args:
        app_bundle: Path to the .app bundle.
        output_path: Output IPA path.
        decrypted_binary: Complete decrypted binary data.
        executable_name: Name of the executable file.

    Returns:
        Path to created IPA.
    """
    work_dir = Path(tempfile.mkdtemp(prefix="orange_ipa_"))

    try:
        # Create Payload structure
        payload_dir = work_dir / "Payload"
        payload_dir.mkdir()

        # Copy app bundle
        dest_app = payload_dir / app_bundle.name
        shutil.copytree(app_bundle, dest_app, symlinks=True)

        # Replace binary
        binary_path = dest_app / executable_name
        binary_path.write_bytes(decrypted_binary)

        # Create ZIP
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in payload_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(payload_dir.parent)
                    zf.write(file_path, arcname)

        return output_path

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
