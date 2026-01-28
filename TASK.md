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

### Phase 3.5: Streaming Content Playback (2026-01-26) - BLOCKED
- [x] **Netflix/Streaming Content Investigation** - COMPLETE
  - [x] Investigate how Netflix stores downloaded content on iOS
    - Stored in app sandbox: `/var/mobile/Containers/Data/Application/[UUID]/`
  - [x] Determine file locations and formats used
    - HLS segments encrypted with AES-128 CBCS
  - [x] Analyze DRM/encryption mechanisms (FairPlay, Widevine)
    - Apple FairPlay DRM with hardware Secure Enclave
  - [x] Research legal and technical feasibility
    - **NOT FEASIBLE** - Multiple technical and legal barriers
  - [x] Document findings in `docs/streaming-content-research.md`
- [x] **Implementation Assessment** - WON'T IMPLEMENT
  - Reason: DRM protection at content, OS, and hardware levels
  - Legal: DMCA prohibits circumvention
  - Technical: Secure Enclave encryption cannot be bypassed
  - Alternative: Use native Netflix in Linux browser

**Key Findings:**
1. Netflix uses Apple FairPlay DRM (hardware-enforced)
2. AirPlay mirroring shows black screen for DRM content
3. iOS blocks screen recording for streaming apps
4. HDCP enforcement prevents capture via HDMI
5. No legitimate technical path exists

**macOS Apple Silicon Investigation (2026-01-26) - VIABLE PATH FOUND:**
- Apple Silicon Macs (M1/M2/M3/M4) can run iOS apps natively
- PlayCover allows sideloading Netflix iOS app (bypasses App Store block)
- Requires decrypted IPA file (from decrypt.day or jailbroken device)
- **LIMITATION:** Downloads don't transfer - must re-download on Mac
- Netflix iOS app on Mac CAN download content for offline viewing

### Phase 3.6: iOS App Management for macOS (COMPLETE - 2026-01-27)
- [x] **App Discovery & Listing**
  - [x] Add `orange apps list` command to show installed iOS apps
  - [x] Display bundle IDs, versions, sizes, source (App Store/Sideloaded)
  - [x] Add `orange apps search` command for finding apps
  - [x] Add `orange apps info` command for detailed app info
  - [x] Identify extractable apps (User apps only)
  - Files: `orange/core/apps/`, `orange/cli/commands/apps.py`
- [x] **IPA Extraction**
  - [x] Add `orange apps extract <bundle_id>` command
  - [x] Extract IPA from connected device via HouseArrest
  - [x] Warn user about FairPlay encryption
  - [x] Provide guidance for decryption options
- [x] **PlayCover Integration Documentation**
  - [x] Document PlayCover setup workflow
  - [x] Document decrypted IPA sources (decrypt.day)
  - [x] Document frida-ios-dump for jailbroken devices
  - [x] Add `orange apps playcover-guide` command
  - Files: `docs/playcover-integration.md`
- [ ] **Optional: Jailbreak Support** (Deferred)
  - [ ] Integration with frida-ios-dump for IPA decryption
  - [ ] Only for jailbroken devices
  - [ ] Requires user to have Frida installed

**Prerequisites for Netflix on Mac:**
1. Apple Silicon Mac (M1/M2/M3/M4)
2. PlayCover installed (playcover.io)
3. Decrypted Netflix IPA (from decrypt.day or extracted+decrypted)
4. Netflix subscription

### Phase 4: Data Export (COMPLETE - 2026-01-27)
- [x] **Export Module Core**
  - [x] Data models (`Message`, `Contact`, `CalendarEvent`, `Note`)
  - [x] `MessageExporter` - Extract SMS/iMessage from backups
    - Parse sms.db SQLite database
    - Export to JSON, CSV, HTML (chat-style)
    - Filter by contact, date range
    - Get conversation statistics
  - [x] `ContactExporter` - Extract contacts from backups
    - Parse AddressBook.sqlitedb database
    - Export to JSON, CSV, VCF (vCard 3.0)
    - Include phones, emails, addresses
  - [x] `CalendarExporter` - Extract calendar events from backups
    - Parse Calendar.sqlitedb database
    - Export to JSON, CSV, ICS (iCalendar)
    - Support all-day events
  - [x] `NoteExporter` - Extract notes from backups
    - Parse Notes database (iOS 9+ and legacy formats)
    - Export to JSON, CSV, HTML
    - Handle pinned/locked notes
  - Files: `orange/core/export/`
- [x] **CLI Commands**
  - [x] `orange export messages` - Export SMS/iMessage
  - [x] `orange export conversations` - List message conversations
  - [x] `orange export contacts` - Export contacts to VCF/JSON/CSV
  - [x] `orange export calendar` - Export calendar to ICS/JSON/CSV
  - [x] `orange export calendars` - List calendars
  - [x] `orange export notes` - Export notes to HTML/JSON/CSV
  - [x] `orange export folders` - List note folders
  - [x] `orange export summary` - Show exportable data summary
  - Files: `orange/cli/commands/export.py`
- [x] **Test Suite** (104 tests)
  - Files: `tests/core/export/`

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
