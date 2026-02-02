# IPA Decryption Implementation Plan

**Date:** February 1, 2026
**Objective:** Build custom IPA decryption capability into Orange
**Priority Target:** Netflix IPA
**Status:** Planning

---

## Executive Summary

This document outlines the implementation plan for adding IPA decryption capabilities to Orange, eliminating dependency on external tools like TrollDecrypt, Decrypted, or decrypt.day. The implementation will leverage Frida-based memory dumping on jailbroken devices to extract decrypted app binaries at runtime.

---

## Technical Background

### How FairPlay DRM Works

iOS apps downloaded from the App Store are encrypted with Apple's FairPlay DRM:

1. **Encryption**: Apple encrypts the main executable binary using device-specific keys
2. **Storage**: Apps contain `LC_ENCRYPTION_INFO_64` load command marking encrypted sections
3. **Runtime**: iOS kernel decrypts the app into memory when launched
4. **Opportunity**: Once in memory, the decrypted binary can be extracted

### What "Decrypted IPA" Means

A decrypted IPA contains:
- Original app bundle structure
- **Modified executable** with `cryptid = 0` (decrypted flag)
- All frameworks and dylibs in unencrypted form
- All resources, assets, and metadata intact

### Why This Works

FairPlay's security model assumes:
- Users won't jailbreak their devices
- Memory of running processes isn't accessible

Our approach exploits that iOS **must** decrypt the binary to execute it. By attaching to the running process, we can read the already-decrypted memory.

---

## Existing Orange Capabilities

Orange already has comprehensive app management:

| Capability | Status | Location |
|------------|--------|----------|
| App listing | ✅ Complete | `orange/core/apps/manager.py` |
| App search | ✅ Complete | `AppManager.search_apps()` |
| App info | ✅ Complete | `AppManager.get_app()` |
| IPA extraction (encrypted) | ✅ Complete | `AppManager.extract_ipa()` |
| Device connection | ✅ Complete | `orange/core/connection/` |
| Wi-Fi support | ✅ Complete | Wireless.py |

**Gap**: Extracted IPAs remain FairPlay encrypted, requiring external decryption.

---

## Implementation Approaches

### Option A: Frida-Based Decryption (Recommended)

**Description**: Use Frida dynamic instrumentation to dump decrypted memory from running apps.

**Pros**:
- Most mature and well-documented approach
- Works from host machine (macOS/Linux/Windows)
- Active community and updates
- Handles app extensions, frameworks, and dylibs
- No on-device file management needed

**Cons**:
- Requires jailbroken device with Frida server
- Device must run the target app during extraction

**Requirements**:
- Jailbroken iOS device
- Frida server running on device
- SSH access to device
- Target app installed and launchable

### Option B: On-Device Decryption Tool

**Description**: Build or adapt bfdecrypt/Clutch-style tool for on-device extraction.

**Pros**:
- Direct device access (faster for some operations)
- Could work with TrollStore (no traditional jailbreak)

**Cons**:
- Must compile for iOS (Theos/iOS SDK required)
- Limited control from host
- Harder to integrate with Orange's Python codebase

### Option C: Hybrid Approach

**Description**: Support both Frida (host-based) and on-device tools, auto-detecting best option.

**Pros**:
- Maximum compatibility
- Fallback options

**Cons**:
- More complexity
- Two codepaths to maintain

**Recommendation**: Start with **Option A (Frida-based)**, as it integrates naturally with Orange's Python architecture and has the most mature tooling.

---

## Architecture Design

### Module Structure

```
orange/
├── core/
│   ├── apps/
│   │   ├── __init__.py          # Add decrypt exports
│   │   ├── models.py            # Add DecryptedAppInfo model
│   │   ├── manager.py           # Existing app management
│   │   └── decrypt/             # NEW: Decryption module
│   │       ├── __init__.py
│   │       ├── frida_client.py  # Frida connection management
│   │       ├── dumper.py        # Memory dumping logic
│   │       ├── macho.py         # Mach-O binary manipulation
│   │       ├── ipa_builder.py   # IPA reconstruction
│   │       └── exceptions.py    # Decryption-specific errors
│   └── connection/
│       └── jailbreak.py         # NEW: Jailbreak detection/services
├── cli/
│   └── commands/
│       └── apps.py              # Add decrypt subcommand
└── tests/
    └── core/
        └── apps/
            └── decrypt/
                ├── test_frida_client.py
                ├── test_dumper.py
                ├── test_macho.py
                └── test_ipa_builder.py
```

### Class Design

#### FridaClient (frida_client.py)

```python
"""
Manages Frida connection to jailbroken iOS device.
"""
from dataclasses import dataclass
from typing import Optional, Callable
import frida

@dataclass
class FridaDeviceInfo:
    """Information about a Frida-accessible device."""
    id: str
    name: str
    type: str  # 'usb', 'remote', 'local'
    udid: Optional[str]

class FridaClient:
    """Manages Frida connection and session lifecycle."""

    def __init__(self, udid: Optional[str] = None, host: Optional[str] = None):
        """
        Initialize Frida client.

        Args:
            udid: Target device UDID (for USB)
            host: Remote host (for SSH tunnel, e.g., "localhost:27042")
        """
        pass

    def list_devices(self) -> list[FridaDeviceInfo]:
        """List available Frida devices."""
        pass

    def connect(self) -> frida.core.Device:
        """Connect to target device."""
        pass

    def spawn(self, bundle_id: str) -> frida.core.Session:
        """Spawn and attach to an app."""
        pass

    def attach(self, pid: int) -> frida.core.Session:
        """Attach to running process."""
        pass

    def get_running_apps(self) -> list[dict]:
        """List currently running applications."""
        pass

    def close(self) -> None:
        """Clean up Frida connection."""
        pass
```

#### AppDumper (dumper.py)

```python
"""
Extracts decrypted app binaries from device memory.
"""
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

@dataclass
class DumpProgress:
    """Progress information for dump operation."""
    stage: str  # 'spawning', 'attaching', 'dumping', 'downloading', 'building'
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
    frameworks_dumped: list[str]
    extensions_dumped: list[str]
    elapsed_seconds: float

class AppDumper:
    """
    Dumps decrypted iOS applications using Frida.

    This class handles the full workflow:
    1. Spawn/attach to target app
    2. Read encryption info from Mach-O headers
    3. Dump decrypted memory regions
    4. Download app bundle from device
    5. Rebuild IPA with decrypted binaries
    """

    def __init__(
        self,
        frida_client: FridaClient,
        ssh_client: Optional['SSHClient'] = None,
    ):
        """
        Initialize app dumper.

        Args:
            frida_client: Connected Frida client
            ssh_client: Optional SSH client for file operations
        """
        pass

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
            bundle_id: Target app bundle identifier
            output_path: Where to save the decrypted IPA
            include_extensions: Decrypt app extensions
            include_frameworks: Decrypt embedded frameworks
            progress_callback: Optional progress updates

        Returns:
            DumpResult with details about the operation

        Raises:
            AppNotFoundError: App not installed
            AppNotRunningError: Could not spawn app
            DecryptionError: Failed to decrypt binary
        """
        pass

    def _get_encryption_info(self, session: frida.core.Session) -> dict:
        """Read LC_ENCRYPTION_INFO from running process."""
        pass

    def _dump_binary(
        self,
        session: frida.core.Session,
        encryption_info: dict,
    ) -> bytes:
        """Dump decrypted binary from memory."""
        pass

    def _patch_cryptid(self, binary: bytes) -> bytes:
        """Set cryptid to 0 in Mach-O header."""
        pass
```

#### MachOParser (macho.py)

```python
"""
Mach-O binary parsing and manipulation.
"""
from dataclasses import dataclass
from typing import Optional
from enum import IntEnum

class MachOCPUType(IntEnum):
    ARM64 = 0x0100000C
    ARM = 0x0000000C
    X86_64 = 0x01000007

@dataclass
class EncryptionInfo:
    """Encryption information from LC_ENCRYPTION_INFO_64."""
    cryptoff: int      # Offset to encrypted data
    cryptsize: int     # Size of encrypted data
    cryptid: int       # 0 = decrypted, 1 = encrypted

@dataclass
class MachOBinary:
    """Parsed Mach-O binary information."""
    path: str
    cpu_type: MachOCPUType
    is_fat: bool
    slices: list['MachOSlice']
    encryption_info: Optional[EncryptionInfo]

class MachOParser:
    """Parses and manipulates Mach-O binaries."""

    @staticmethod
    def parse(data: bytes) -> MachOBinary:
        """Parse Mach-O binary from bytes."""
        pass

    @staticmethod
    def get_encryption_info(data: bytes) -> Optional[EncryptionInfo]:
        """Extract encryption info from binary."""
        pass

    @staticmethod
    def patch_cryptid(data: bytes, new_cryptid: int = 0) -> bytes:
        """Patch the cryptid field in LC_ENCRYPTION_INFO."""
        pass

    @staticmethod
    def is_encrypted(data: bytes) -> bool:
        """Check if binary is FairPlay encrypted."""
        pass
```

#### IPABuilder (ipa_builder.py)

```python
"""
Reconstructs IPA files from decrypted components.
"""
from pathlib import Path
from typing import Optional
import zipfile

class IPABuilder:
    """Builds IPA files from app components."""

    def __init__(self, work_dir: Optional[Path] = None):
        """
        Initialize IPA builder.

        Args:
            work_dir: Temporary directory for assembly
        """
        pass

    def build(
        self,
        app_bundle_path: Path,
        output_path: Path,
        decrypted_binaries: dict[str, bytes],
    ) -> Path:
        """
        Build IPA from app bundle with decrypted binaries.

        Args:
            app_bundle_path: Path to extracted .app bundle
            output_path: Where to save the IPA
            decrypted_binaries: Map of relative paths to decrypted binary data

        Returns:
            Path to created IPA file
        """
        pass

    def _create_payload(self, app_path: Path) -> Path:
        """Create Payload directory structure."""
        pass

    def _replace_binaries(
        self,
        payload_path: Path,
        decrypted_binaries: dict[str, bytes],
    ) -> None:
        """Replace encrypted binaries with decrypted versions."""
        pass

    def _compress_ipa(self, payload_path: Path, output_path: Path) -> Path:
        """Compress Payload into IPA (ZIP) format."""
        pass
```

### CLI Integration

```python
# In orange/cli/commands/apps.py

@apps.command("decrypt")
@click.argument("bundle_id")
@click.argument("output", type=click.Path())
@click.option("--udid", help="Target device UDID")
@click.option("--host", help="Frida remote host (e.g., localhost:27042)")
@click.option("--no-extensions", is_flag=True, help="Skip app extensions")
@click.option("--no-frameworks", is_flag=True, help="Skip embedded frameworks")
@click.pass_context
def decrypt_app(ctx, bundle_id, output, udid, host, no_extensions, no_frameworks):
    """
    Extract a decrypted IPA from a jailbroken device.

    Requires:
    - Jailbroken iOS device with Frida server installed
    - SSH access to device (or Frida remote connection)
    - Target app must be installed on device

    Example:
        orange apps decrypt com.netflix.Netflix ./netflix-decrypted.ipa
    """
    pass
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)

**Objective**: Establish Frida connectivity and basic device interaction.

**Tasks**:
1. Add `frida-tools` dependency to requirements.txt
2. Implement `FridaClient` class
3. Add jailbreak detection to connection module
4. Create basic CLI structure for decrypt command
5. Write unit tests with mocked Frida

**Deliverables**:
- `orange/core/apps/decrypt/frida_client.py`
- `orange/core/connection/jailbreak.py`
- `tests/core/apps/decrypt/test_frida_client.py`

### Phase 2: Mach-O Handling (Week 2)

**Objective**: Parse and manipulate Mach-O binaries.

**Tasks**:
1. Implement `MachOParser` for reading encryption info
2. Implement `cryptid` patching
3. Handle FAT (universal) binaries
4. Support both ARM64 and ARM64e architectures
5. Write comprehensive tests

**Deliverables**:
- `orange/core/apps/decrypt/macho.py`
- `tests/core/apps/decrypt/test_macho.py`
- Test fixtures with sample encrypted/decrypted binaries

### Phase 3: Memory Dumping (Week 3)

**Objective**: Extract decrypted binaries from running apps.

**Tasks**:
1. Create Frida injection script for memory reading
2. Implement `AppDumper._dump_binary()`
3. Handle encrypted section extraction
4. Support app extensions and frameworks
5. Add progress reporting

**Deliverables**:
- `orange/core/apps/decrypt/dumper.py`
- `orange/core/apps/decrypt/scripts/dump.js` (Frida script)
- `tests/core/apps/decrypt/test_dumper.py`

### Phase 4: IPA Reconstruction (Week 4)

**Objective**: Build complete IPAs from dumped components.

**Tasks**:
1. Implement `IPABuilder` class
2. Integrate SSH file transfer (leverage existing connection module)
3. Handle binary replacement in app bundle
4. Create proper IPA ZIP structure
5. End-to-end integration testing

**Deliverables**:
- `orange/core/apps/decrypt/ipa_builder.py`
- `tests/core/apps/decrypt/test_ipa_builder.py`
- Integration tests with real device (manual)

### Phase 5: CLI & Documentation (Week 5)

**Objective**: Complete user-facing features and documentation.

**Tasks**:
1. Implement `orange apps decrypt` command
2. Add progress visualization (Rich)
3. Error handling and user-friendly messages
4. Update documentation
5. Add troubleshooting guide

**Deliverables**:
- Updated `orange/cli/commands/apps.py`
- `docs/ipa-decryption-guide.md`
- Updated `README.md`

### Phase 6: Netflix Testing & Refinement (Week 6)

**Objective**: Validate with Netflix and refine.

**Tasks**:
1. Test decryption with Netflix IPA
2. Verify decrypted IPA works with PlayCover
3. Test with various iOS versions (15, 16, 17, 18)
4. Performance optimization
5. Edge case handling

**Deliverables**:
- Netflix-specific validation report
- Performance benchmarks
- Known issues documentation

---

## Dependencies

### Required New Dependencies

```txt
# requirements.txt additions
frida-tools>=12.0.0      # Frida Python bindings
paramiko>=3.0.0          # SSH for file transfer (if not using existing)
```

### Device Requirements

| Requirement | Details |
|-------------|---------|
| Jailbreak | Any jailbreak that allows Frida (unc0ver, checkra1n, Dopamine, etc.) |
| Frida Server | Must be installed on device (via Cydia/Sileo/Zebra) |
| iOS Version | 13.0 - 18.x (depending on jailbreak availability) |
| SSH | OpenSSH or Dropbear for file transfer |

---

## Risk Mitigation

### Technical Risks

| Risk | Mitigation |
|------|------------|
| Frida detection by apps | Use Frida Gadget or spawn-gating techniques |
| iOS version incompatibility | Test matrix across versions, graceful fallbacks |
| Binary format changes | Abstract Mach-O handling, version-specific parsers |
| App-specific protections | Document known problematic apps |

### Legal Considerations

| Activity | Status | Notes |
|----------|--------|-------|
| Jailbreaking | ✅ Legal (US) | DMCA exemption for personal devices |
| Decrypting owned apps | ⚠️ Gray area | For personal backup/interoperability |
| Distribution of decrypted IPAs | ❌ Illegal | Not supported by Orange |

**Orange's Position**:
- Tool enables users to decrypt apps **they own**
- No piracy facilitation (no IPA distribution)
- Clear documentation of legal boundaries
- User assumes responsibility for compliance

---

## Success Criteria

### Functional Requirements

- [ ] Decrypt single-binary iOS apps
- [ ] Decrypt apps with embedded frameworks
- [ ] Decrypt apps with extensions
- [ ] Handle FAT (universal) binaries
- [ ] Support USB and remote Frida connections
- [ ] Progress reporting during long operations
- [ ] Graceful error handling with actionable messages

### Performance Targets

| Metric | Target |
|--------|--------|
| Decryption time (small app) | < 30 seconds |
| Decryption time (Netflix ~100MB) | < 5 minutes |
| Memory usage (host) | < 500MB |

### Quality Requirements

- [ ] 80%+ code coverage
- [ ] Type hints throughout
- [ ] Documentation for all public APIs
- [ ] Integration tests with real device
- [ ] CI/CD pipeline validation

---

## Reference Implementations

### GitHub Repositories for Reference

| Repository | Focus | Usefulness |
|------------|-------|------------|
| [AloneMonkey/frida-ios-dump](https://github.com/AloneMonkey/frida-ios-dump) | Primary reference | Core dumping logic |
| [ChiChou/bagbak](https://github.com/ChiChou/bagbak) | Extensions handling | Multi-binary support |
| [lautarovculic/frida-ipa-extract](https://github.com/lautarovculic/frida-ipa-extract) | Robust variant | Error handling patterns |
| [NyaMisty/fouldecrypt](https://github.com/NyaMisty/fouldecrypt) | On-device decryption | Alternative approach |
| [qyang-nj/llios](https://github.com/qyang-nj/llios) | Mach-O documentation | Binary format reference |

### Key Code Patterns from frida-ios-dump

```python
# Example: Reading encryption info via Frida
script = session.create_script("""
    var modules = Process.enumerateModules();
    var main = modules[0];

    // Read Mach-O header
    var header = main.base;
    var magic = Memory.readU32(header);

    // Find LC_ENCRYPTION_INFO_64
    // ... (traverse load commands)

    send({
        'cryptoff': cryptoff,
        'cryptsize': cryptsize,
        'cryptid': cryptid
    });
""")
```

---

## Timeline Summary

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1 | Foundation | Frida client, jailbreak detection |
| 2 | Mach-O | Binary parsing and patching |
| 3 | Dumping | Memory extraction, Frida scripts |
| 4 | Building | IPA reconstruction |
| 5 | Polish | CLI, documentation |
| 6 | Validation | Netflix testing, refinement |

**Total Estimated Duration**: 6 weeks

---

## Next Steps

1. **Review this plan** with stakeholders
2. **Set up test environment**:
   - Jailbroken iOS device
   - Frida server installation
   - SSH access configured
3. **Begin Phase 1** implementation
4. **Create tracking task** in TASK.md

---

## Appendix: Frida Dump Script Reference

```javascript
// Core dumping script (simplified)
function dumpModule(module) {
    var header = module.base;
    var cryptoff = null;
    var cryptsize = null;

    // Parse Mach-O header
    var magic = Memory.readU32(header);
    var ncmds = Memory.readU32(header.add(16));
    var cmdptr = header.add(32); // After header

    // Find encryption info
    for (var i = 0; i < ncmds; i++) {
        var cmd = Memory.readU32(cmdptr);
        var cmdsize = Memory.readU32(cmdptr.add(4));

        if (cmd === 0x2C) { // LC_ENCRYPTION_INFO_64
            cryptoff = Memory.readU32(cmdptr.add(8));
            cryptsize = Memory.readU32(cmdptr.add(12));
            break;
        }
        cmdptr = cmdptr.add(cmdsize);
    }

    if (cryptoff && cryptsize) {
        // Read decrypted region from memory
        var decrypted = Memory.readByteArray(
            module.base.add(cryptoff),
            cryptsize
        );
        return decrypted;
    }
    return null;
}
```

---

*Document Version: 1.0*
*Last Updated: February 1, 2026*
