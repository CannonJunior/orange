# Orange

**Cross-platform iOS file transfer and data management for Mac, Windows, and Linux.**

Orange is an open-source tool for transferring messages, music, files, and data between iPhone/iPad and your computer - without iTunes or iCloud.

## Features

- **Device Connection** - USB and Wi-Fi device detection with secure pairing ✅ *Available*
- **Full Backup & Restore** - Create and restore iOS backups ✅ *Available*
- **Backup Browser** - Browse and extract files from backups ✅ *Available*
- **File Transfer** - Bidirectional transfer of photos, videos, music, and documents ✅ *Available*
- **Category Backup** - Selectively backup photos, music, books, or other categories ✅ *Available*
- **Data Export** - Extract messages, contacts, calendar, and notes to PDF/CSV/JSON *(Planned)*
- **Format Conversion** - Convert FLAC to ALAC, HEIC to JPEG, and more *(Planned)*
- **Cross-Platform** - Works on macOS, Windows, and Linux

## Status

**Current Phase:** Phase 3 In Progress

- [x] Literature Review - Completed
- [x] Implementation Plan - Completed
- [x] Phase 1: Connection Module - **Complete** (65 tests)
- [x] Phase 2: Backup Engine - **Complete** (42 tests)
  - [x] Backup creation and restoration
  - [x] Backup listing and info
  - [x] File browsing and extraction
  - [ ] Encrypted backup decryption
- [x] Phase 3: File Transfer - **In Progress** (56 tests)
  - [x] Category-based selective transfer (photos, music, books, etc.)
  - [x] Direct file browsing and transfer via AFC
  - [ ] Format conversion
- [ ] Phase 4: Data Extraction
- [ ] Phase 5: Format Conversion
- [ ] Phase 6: Export & Distribution

## Quick Start

```bash
# Clone the repository
git clone <repo-url>
cd orange

# Create virtual environment
python3 -m venv venv_linux
source venv_linux/bin/activate  # Linux/macOS
# or: venv_linux\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Run Orange
orange --help
```

## Usage

### Device Management (Phase 1 - Available Now)

```bash
# List connected iOS devices (USB + Wi-Fi)
orange device list
orange device list --json

# Show device information (UDID optional if single device)
orange device info
orange device info --all

# Pair with a device (one-time, requires USB)
orange device pair

# Test connection
orange device ping
```

### Wi-Fi Sync Setup (No Developer Mode Required)

Orange uses Apple's standard Wi-Fi Sync protocol - the same one used by iTunes and Finder.

```bash
# One-time setup (device connected via USB):
orange device pair              # Pair with device
orange device wifi --enable     # Enable Wi-Fi connections

# After setup, disconnect USB and use wirelessly:
orange device scan              # Discover Wi-Fi devices on network
orange device list              # Shows both USB and Wi-Fi devices
```

### Backup Management (Phase 2 - Available Now)

```bash
# Create a backup of your device
orange backup create

# Create backup to specific location
orange backup create --output ./my-backups

# List all backups
orange backup list

# Show backup details
orange backup info ./backups/device-udid

# Browse files in a backup
orange backup browse ./backups/device-udid
orange backup browse ./backups/device-udid --domain HomeDomain

# Extract a file from backup
orange backup extract ./backups/device-udid --domain HomeDomain -f "Library/SMS/sms.db" -o ./extracted

# Restore a backup
orange backup restore ./backups/device-udid

# Delete a backup
orange backup delete ./backups/device-udid
```

### File Transfer (Phase 3 - Available Now)

Transfer files directly without creating a full backup using AFC (Apple File Conduit).

```bash
# List available data categories
orange files categories

# Browse files on device
orange files browse
orange files browse /DCIM
orange files browse /DCIM/100APPLE --json

# Pull (download) files from device
orange files pull /DCIM/100APPLE ./photos

# Pull entire category (photos, music, books, etc.)
orange files pull-category photos ./my-photos
orange files pull-category music ./my-music

# Push (upload) files to device
orange files push ./songs /iTunes_Control/Music

# Show file info
orange files info /DCIM/100APPLE/IMG_0001.HEIC

# Check category size before downloading
orange files size photos
```

**Note:** Some data categories (Messages, Contacts, Health, etc.) require backup access. Use `orange backup create` for these.

### Coming Soon (Phases 4-6)

```bash
# Export messages to PDF
orange export messages <backup-id> --format pdf --output messages.pdf

# Format conversion
orange convert ./photo.heic --format jpeg
```

## Requirements

- Python 3.10+
- macOS, Windows, or Linux
- iOS device (iPhone, iPad, or iPod touch)
- USB cable or Wi-Fi sync enabled

### Windows Note

On Windows, iTunes or Apple Mobile Device Support must be installed for USB communication.

## Architecture

Orange is built as a modular library with reusable components:

```
orange/
├── core/
│   ├── connection/   # Device detection & pairing
│   ├── backup/       # Backup creation & restore
│   ├── transfer/     # File transfer via AFC
│   ├── data/         # Data extraction (messages, contacts)
│   ├── convert/      # Media format conversion
│   └── export/       # Export formatters (PDF, CSV, JSON)
└── cli/              # Command-line interface
```

Each module can be used independently, enabling integration into other applications.

## Documentation

- [Literature Review](docs/literature-review-ios-emulation.md) - Analysis of existing tools and technologies
- [Implementation Plan](PLANNING.md) - Detailed technical specifications
- [Task Tracking](TASK.md) - Current development status

## Technology Stack

- **Language:** Python 3.10+
- **iOS Protocol:** [pymobiledevice3](https://github.com/doronz88/pymobiledevice3)
- **CLI Framework:** [Click](https://click.palletsprojects.com/)
- **Encryption:** [PyCryptodome](https://pycryptodome.readthedocs.io/)

## Legal

Orange uses publicly documented iOS protocols for device communication. The project relies on the [libimobiledevice](https://libimobiledevice.org/) ecosystem, which has operated under DMCA interoperability exemptions since 2007.

**No jailbreak required.** Orange works with stock iOS devices.

## Contributing

Contributions are welcome! Please read the implementation plan in `PLANNING.md` before starting work.

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Submit a pull request

## License

[MIT License](LICENSE)

## Acknowledgments

- [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) - Pure Python iOS device protocols
- [libimobiledevice](https://libimobiledevice.org/) - The foundational open-source iOS library
- [The iPhone Wiki](https://www.theiphonewiki.com/) - Protocol documentation

---

*Orange is not affiliated with Apple Inc. iPhone, iPad, and iOS are trademarks of Apple Inc.*
