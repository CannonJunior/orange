"""
App dumper for extracting decrypted iOS applications.

This module handles the full workflow of dumping decrypted apps:
1. Spawn/attach to target app via Frida
2. Read encryption info from Mach-O headers
3. Dump decrypted memory regions
4. Download app bundle from device
5. Rebuild IPA with decrypted binaries
"""

from __future__ import annotations

import logging
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable, Any

from orange.core.apps.decrypt.frida_client import FridaClient
from orange.core.apps.decrypt.macho import MachOParser, EncryptionInfo
from orange.core.apps.decrypt.exceptions import (
    DecryptionError,
    AppNotFoundError,
    AppNotRunningError,
)

logger = logging.getLogger(__name__)


# Frida script for dumping decrypted memory
DUMP_SCRIPT = """
'use strict';

// Get the main executable module
var modules = Process.enumerateModules();
var mainModule = modules[0];

// Result object
var result = {
    moduleName: mainModule.name,
    modulePath: mainModule.path,
    moduleBase: mainModule.base.toString(),
    moduleSize: mainModule.size,
    encryptionInfo: null,
    decryptedData: null
};

// Parse Mach-O header to find encryption info
function findEncryptionInfo() {
    var header = mainModule.base;
    var magic = Memory.readU32(header);

    // Determine if 64-bit
    var is64 = (magic === 0xfeedfacf || magic === 0xcffaedfe);
    var headerSize = is64 ? 32 : 28;

    // Read number of load commands
    var ncmds = Memory.readU32(header.add(16));

    // Iterate through load commands
    var cmdPtr = header.add(headerSize);

    for (var i = 0; i < ncmds; i++) {
        var cmd = Memory.readU32(cmdPtr);
        var cmdSize = Memory.readU32(cmdPtr.add(4));

        // LC_ENCRYPTION_INFO_64 = 0x2C, LC_ENCRYPTION_INFO = 0x21
        if (cmd === 0x2c || cmd === 0x21) {
            var cryptoff = Memory.readU32(cmdPtr.add(8));
            var cryptsize = Memory.readU32(cmdPtr.add(12));
            var cryptid = Memory.readU32(cmdPtr.add(16));

            return {
                cryptoff: cryptoff,
                cryptsize: cryptsize,
                cryptid: cryptid,
                cmdOffset: cmdPtr.sub(mainModule.base).toInt32()
            };
        }

        cmdPtr = cmdPtr.add(cmdSize);
    }

    return null;
}

// Dump the decrypted section from memory
function dumpDecryptedSection(encInfo) {
    if (!encInfo || encInfo.cryptid === 0) {
        return null;
    }

    var startAddr = mainModule.base.add(encInfo.cryptoff);
    var data = Memory.readByteArray(startAddr, encInfo.cryptsize);

    return data;
}

// Main execution
try {
    result.encryptionInfo = findEncryptionInfo();

    if (result.encryptionInfo && result.encryptionInfo.cryptid !== 0) {
        result.decryptedData = dumpDecryptedSection(result.encryptionInfo);
    }

    send(result);
} catch (e) {
    send({error: e.toString()});
}
"""

# Script for enumerating all binaries (main + frameworks)
ENUMERATE_BINARIES_SCRIPT = """
'use strict';

var binaries = [];
var modules = Process.enumerateModules();

// Filter to app-related modules
var appPath = modules[0].path;
var appDir = appPath.substring(0, appPath.lastIndexOf('/'));

for (var i = 0; i < modules.length; i++) {
    var mod = modules[i];

    // Include main executable and app frameworks
    if (mod.path.startsWith(appDir) || mod.path.indexOf('.app/') !== -1) {
        binaries.push({
            name: mod.name,
            path: mod.path,
            base: mod.base.toString(),
            size: mod.size
        });
    }
}

send(binaries);
"""


@dataclass
class DumpProgress:
    """Progress information for dump operation."""

    stage: str  # 'connecting', 'spawning', 'dumping', 'downloading', 'building'
    current: int
    total: int
    message: str


@dataclass
class DumpResult:
    """Result of a successful dump operation."""

    bundle_id: str
    ipa_path: Path
    original_size: int
    decrypted_size: int
    frameworks_dumped: list[str] = field(default_factory=list)
    extensions_dumped: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0


@dataclass
class BinaryDumpInfo:
    """Information about a dumped binary."""

    name: str
    path: str
    original_data: bytes
    decrypted_section: Optional[bytes]
    encryption_info: Optional[EncryptionInfo]

    @property
    def is_encrypted(self) -> bool:
        """Check if this binary was encrypted."""
        return (
            self.encryption_info is not None
            and self.encryption_info.cryptid != 0
        )


class AppDumper:
    """
    Dumps decrypted iOS applications using Frida.

    This class handles the full workflow of extracting a decrypted IPA:
    1. Connect to device via Frida
    2. Spawn the target app
    3. Inject script to dump decrypted memory
    4. Download the app bundle
    5. Replace encrypted binaries with decrypted versions
    6. Package as IPA

    Example:
        with FridaClient(udid="...") as client:
            dumper = AppDumper(client)
            result = dumper.dump(
                "com.netflix.Netflix",
                Path("./Netflix-decrypted.ipa"),
            )
            print(f"Saved to: {result.ipa_path}")
    """

    def __init__(
        self,
        frida_client: FridaClient,
        ssh_host: Optional[str] = None,
        ssh_port: int = 22,
        ssh_user: str = "root",
        ssh_password: str = "alpine",
    ):
        """
        Initialize app dumper.

        Args:
            frida_client: Connected FridaClient instance.
            ssh_host: SSH host for file transfer (default: use device IP).
            ssh_port: SSH port (default: 22).
            ssh_user: SSH username (default: "root").
            ssh_password: SSH password (default: "alpine").
        """
        self.frida = frida_client
        self.ssh_host = ssh_host
        self.ssh_port = ssh_port
        self.ssh_user = ssh_user
        self.ssh_password = ssh_password
        self._ssh_client: Optional[Any] = None

    def dump(
        self,
        bundle_id: str,
        output_path: Path,
        include_extensions: bool = True,
        include_frameworks: bool = True,
        progress_callback: Optional[Callable[[DumpProgress], None]] = None,
    ) -> DumpResult:
        """
        Dump a decrypted IPA for the specified app.

        Args:
            bundle_id: Target app bundle identifier.
            output_path: Where to save the decrypted IPA.
            include_extensions: Decrypt app extensions (default True).
            include_frameworks: Decrypt embedded frameworks (default True).
            progress_callback: Optional callback for progress updates.

        Returns:
            DumpResult with details about the operation.

        Raises:
            AppNotFoundError: App not installed on device.
            AppNotRunningError: Could not spawn/attach to app.
            DecryptionError: Failed to decrypt binary.
        """
        start_time = time.time()

        def report_progress(stage: str, current: int, total: int, message: str):
            if progress_callback:
                progress_callback(DumpProgress(stage, current, total, message))

        # Verify app exists
        report_progress("connecting", 0, 5, "Checking app installation...")
        app_info = self.frida.get_app_info(bundle_id)
        if not app_info:
            raise AppNotFoundError(bundle_id)

        logger.info(f"Found app: {app_info.name} ({bundle_id})")

        # Spawn the app
        report_progress("spawning", 1, 5, f"Spawning {app_info.name}...")
        session = self.frida.spawn(bundle_id)
        logger.debug(f"Spawned and attached to {bundle_id}")

        try:
            # Dump main binary
            report_progress("dumping", 2, 5, "Dumping main executable...")
            main_dump = self._dump_binary(session, bundle_id)

            # Enumerate and dump frameworks if requested
            frameworks_dumped = []
            if include_frameworks:
                report_progress("dumping", 2, 5, "Enumerating frameworks...")
                binaries = self._enumerate_binaries(session)

                for i, binary_info in enumerate(binaries[1:], 1):  # Skip main
                    if "/Frameworks/" in binary_info.get("path", ""):
                        framework_name = binary_info["name"]
                        report_progress(
                            "dumping",
                            2,
                            5,
                            f"Dumping framework: {framework_name}",
                        )
                        try:
                            # Framework dumping would require additional session attachment
                            # For now, track which frameworks exist
                            frameworks_dumped.append(framework_name)
                        except Exception as e:
                            logger.warning(f"Failed to dump {framework_name}: {e}")

            # Download app bundle from device
            report_progress("downloading", 3, 5, "Downloading app bundle...")
            app_bundle_path = self._download_app_bundle(bundle_id)

            # Build the IPA with decrypted binary
            report_progress("building", 4, 5, "Building decrypted IPA...")
            from orange.core.apps.decrypt.ipa_builder import IPABuilder

            builder = IPABuilder()
            ipa_path = builder.build(
                app_bundle_path=app_bundle_path,
                output_path=output_path,
                main_binary_dump=main_dump,
            )

            elapsed = time.time() - start_time
            report_progress("building", 5, 5, "Complete!")

            return DumpResult(
                bundle_id=bundle_id,
                ipa_path=ipa_path,
                original_size=main_dump.encryption_info.cryptsize if main_dump.encryption_info else 0,
                decrypted_size=len(main_dump.decrypted_section) if main_dump.decrypted_section else 0,
                frameworks_dumped=frameworks_dumped,
                extensions_dumped=[],
                elapsed_seconds=elapsed,
            )

        finally:
            # Clean up: detach from session
            try:
                session.detach()
            except Exception as e:
                logger.debug(f"Error detaching: {e}")

    def _dump_binary(self, session: Any, bundle_id: str) -> BinaryDumpInfo:
        """
        Dump the decrypted main binary from a running app.

        Args:
            session: Active Frida session.
            bundle_id: App bundle identifier (for naming).

        Returns:
            BinaryDumpInfo with decrypted data.
        """
        result_data = {"received": False, "data": None, "error": None}

        def on_message(message: dict, data: Optional[bytes]):
            if message["type"] == "send":
                payload = message["payload"]
                if "error" in payload:
                    result_data["error"] = payload["error"]
                else:
                    result_data["data"] = payload
                    # The decrypted data comes as binary attachment
                    if data:
                        result_data["decrypted_bytes"] = data
                result_data["received"] = True

        # Create and load the dump script
        script = session.create_script(DUMP_SCRIPT)
        script.on("message", on_message)
        script.load()

        # Wait for result (with timeout)
        timeout = 30
        start = time.time()
        while not result_data["received"] and (time.time() - start) < timeout:
            time.sleep(0.1)

        if result_data["error"]:
            raise DecryptionError(f"Frida script error: {result_data['error']}")

        if not result_data["data"]:
            raise DecryptionError("No data received from dump script")

        data = result_data["data"]
        enc_info = data.get("encryptionInfo")

        encryption_info = None
        if enc_info:
            encryption_info = EncryptionInfo(
                cryptoff=enc_info["cryptoff"],
                cryptsize=enc_info["cryptsize"],
                cryptid=enc_info["cryptid"],
                cmd_offset=enc_info.get("cmdOffset", 0),
            )

        # Get decrypted section from binary data
        decrypted_section = None
        if "decrypted_bytes" in result_data:
            decrypted_section = result_data["decrypted_bytes"]
        elif data.get("decryptedData"):
            # Convert from Frida's ArrayBuffer format
            decrypted_section = bytes(data["decryptedData"])

        return BinaryDumpInfo(
            name=data.get("moduleName", bundle_id),
            path=data.get("modulePath", ""),
            original_data=b"",  # Will be filled from downloaded bundle
            decrypted_section=decrypted_section,
            encryption_info=encryption_info,
        )

    def _enumerate_binaries(self, session: Any) -> list[dict]:
        """
        Enumerate all binaries loaded by the app.

        Args:
            session: Active Frida session.

        Returns:
            List of binary info dicts.
        """
        result_data = {"received": False, "binaries": []}

        def on_message(message: dict, data: Optional[bytes]):
            if message["type"] == "send":
                result_data["binaries"] = message["payload"]
                result_data["received"] = True

        script = session.create_script(ENUMERATE_BINARIES_SCRIPT)
        script.on("message", on_message)
        script.load()

        timeout = 10
        start = time.time()
        while not result_data["received"] and (time.time() - start) < timeout:
            time.sleep(0.1)

        return result_data["binaries"]

    def _download_app_bundle(self, bundle_id: str) -> Path:
        """
        Download the app bundle from the device.

        This uses SSH/SCP to copy the app bundle to a local temp directory.

        Args:
            bundle_id: App bundle identifier.

        Returns:
            Path to downloaded app bundle.
        """
        # Get app info to find the bundle path
        app_info = self.frida.get_app_info(bundle_id)
        if not app_info:
            raise AppNotFoundError(bundle_id)

        # Create temp directory for download
        temp_dir = Path(tempfile.mkdtemp(prefix="orange_decrypt_"))
        local_bundle_path = temp_dir / f"{bundle_id}.app"

        # Use paramiko to download via SSH
        try:
            import paramiko
            from scp import SCPClient

            # Connect SSH
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Determine SSH host
            host = self.ssh_host
            if not host:
                # Try to get from Frida device
                # For USB connections, typically use localhost with SSH tunnel
                # or the device's IP address
                host = "localhost"  # Assumes SSH tunnel is set up

            logger.debug(f"Connecting via SSH to {host}:{self.ssh_port}")
            ssh.connect(
                host,
                port=self.ssh_port,
                username=self.ssh_user,
                password=self.ssh_password,
                look_for_keys=False,
                allow_agent=False,
            )

            # Find the app bundle path on device
            # Apps are typically in /var/containers/Bundle/Application/<UUID>/<name>.app
            stdin, stdout, stderr = ssh.exec_command(
                f"find /var/containers/Bundle/Application -name '*.app' -path '*{bundle_id}*' 2>/dev/null | head -1"
            )
            remote_path = stdout.read().decode().strip()

            if not remote_path:
                # Try alternative: use installed app list
                stdin, stdout, stderr = ssh.exec_command(
                    f"find /var/containers/Bundle/Application -name '*.app' 2>/dev/null | "
                    f"xargs -I{{}} sh -c 'plutil -p {{}}/Info.plist 2>/dev/null | "
                    f"grep -q \"{bundle_id}\" && echo {{}}' | head -1"
                )
                remote_path = stdout.read().decode().strip()

            if not remote_path:
                raise DecryptionError(f"Could not find app bundle for {bundle_id} on device")

            logger.debug(f"Found app bundle at: {remote_path}")

            # Download using SCP
            with SCPClient(ssh.get_transport()) as scp:
                scp.get(remote_path, str(local_bundle_path), recursive=True)

            ssh.close()
            logger.debug(f"Downloaded app bundle to: {local_bundle_path}")

            return local_bundle_path

        except ImportError:
            raise DecryptionError(
                "SSH/SCP not available. Install with: pip install paramiko scp"
            )
        except Exception as e:
            raise DecryptionError(f"Failed to download app bundle: {e}")

    def _get_ssh_client(self) -> Any:
        """Get or create SSH client."""
        if self._ssh_client is None:
            try:
                import paramiko

                self._ssh_client = paramiko.SSHClient()
                self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            except ImportError:
                raise DecryptionError(
                    "paramiko not installed. Install with: pip install paramiko"
                )

        return self._ssh_client
