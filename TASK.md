# Orange Project - Task Tracking

## Current Tasks

### Phase 0: Research & Planning
- [x] **Literature Review** (2026-01-25)
  - Analyzed commercial competitors (WALTR PRO, iMazing, AnyTrans)
  - Reviewed open-source ecosystem (libimobiledevice, pymobiledevice3)
  - Documented technical protocols (AFC, usbmuxd, lockdown)
  - Assessed legal/compliance framework
  - Evaluated distribution options
  - Provided modular architecture recommendations
  - Output: `docs/literature-review-ios-emulation.md`

- [x] **Implementation Plan** (2026-01-25)
  - Created detailed implementation plan with 6 phases
  - Defined MVP scope (Phase 1: Connection Module)
  - Specified module interfaces and class designs
  - Documented testing strategy and coding standards
  - Output: `PLANNING.md`

### Phase 1: Foundation (Completed 2026-01-25)
- [x] Device Connection Module
  - [x] USB device detection (`DeviceDetector`, `DeviceInfo`)
  - [x] Pairing/trust workflow (`PairingManager`, `PairingState`)
  - [x] Wi-Fi device discovery (integrated in `DeviceDetector`)
  - [x] Connection state management (`ConnectionManager`, `DeviceConnection`)
  - [x] CLI commands (`orange device list/info/pair/unpair/ping`)
  - [x] Test suite (65 tests, 72% coverage)
  - Files: `orange/core/connection/`, `orange/cli/commands/device.py`

### Phase 2: Backup & Restore (In Progress 2026-01-25)
- [x] Backup Engine Core
  - [x] `BackupManager` - Create/restore/list backups
  - [x] `BackupReader` - Parse backup contents, extract files
  - [x] `BackupInfo`, `BackupFile` models
  - [x] CLI commands (`orange backup create/restore/list/info/browse/extract/delete`)
  - [x] Test suite (42 tests)
  - Files: `orange/core/backup/`, `orange/cli/commands/backup.py`
- [ ] Remaining
  - [ ] Encrypted backup decryption (password-protected extraction)
  - [ ] Progress callbacks for large operations
  - [ ] Incremental backup support

### Phase 3: File Transfer (In Progress 2026-01-25)
- [x] Transfer Module Core
  - [x] `DeviceBrowser` - Browse files on device via AFC
  - [x] `FileManager` - Pull/push files and directories
  - [x] `DataCategory` - Category-based selective transfer
  - [x] Categories defined: photos, music, books, downloads, recordings, podcasts
  - [x] CLI commands (`orange files browse/pull/push/pull-category/categories/size/info`)
  - [x] Test suite (56 tests)
  - Files: `orange/core/transfer/`, `orange/cli/commands/files.py`
- [ ] Remaining
  - [ ] Format conversion (HEIC->JPEG, FLAC->ALAC)
  - [ ] Batch operations with filters
  - [ ] Media library sync

### Phase 4: Data Export (Planned)
- [ ] Data Extraction
  - [ ] Message export
  - [ ] Contact export
  - [ ] Calendar/Notes export

### Phase 5: Distribution (Planned)
- [ ] Packaging
  - [ ] macOS notarization
  - [ ] Windows installer
  - [ ] Linux packages (AppImage/Flatpak)

---

## Discovered During Work

### From Literature Review (2026-01-25)
- Health data module should be a separate sub-project requiring iOS companion app
- Linux support is an underserved market (none of the major competitors support it)
- Mac App Store sandboxing prevents full-featured iOS managers; direct distribution recommended
- pymobiledevice3 is recommended over libimobiledevice for Python-native development
- iOS 17+ uses new XPC-based protocols requiring updated handling

### From Phase 1 Implementation (2026-01-25)
- `orange device scan` shows Device Name but Model/iOS/UDID columns are empty
  - Deferred to backlog: see `BACKLOG-TODO-LIST.md`
  - Attempted fix broke discovery entirely; reverted

---

## Notes

- All development should use the `venv_linux` virtual environment
- Web services run on port 9091
- Tests in `/tests` directory mirroring main app structure
