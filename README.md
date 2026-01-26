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

### Starting Services (Linux)

On Linux, run the startup script to ensure required services are running:

```bash
./start.sh
```

This checks that `usbmuxd` is running (required for iOS communication).

---

### Device Management

Manage connections to iOS devices over USB and Wi-Fi.

#### List Devices

```bash
# List all connected devices
orange device list

# Output as JSON (for scripting)
orange device list --json

# Include Wi-Fi devices in listing
orange device list --wifi
```

#### Device Information

```bash
# Show info for connected device (auto-selects if only one)
orange device info

# Show all available device properties
orange device info --all

# Show info for specific device by UDID
orange device info 00008110-001234567890
```

#### Pairing

```bash
# Pair with device (requires USB, one-time setup)
orange device pair

# Check if device is paired
orange device is-paired

# Unpair a device
orange device unpair
```

#### Connection Testing

```bash
# Test connection to device
orange device ping

# Ping specific device
orange device ping --udid 00008110-001234567890
```

#### Wi-Fi Sync Setup

Orange uses Apple's standard Wi-Fi Sync protocol (no Developer Mode required).

```bash
# One-time setup (device connected via USB):
orange device pair              # Pair with device
orange device wifi --enable     # Enable Wi-Fi connections

# After setup, disconnect USB and use wirelessly:
orange device scan              # Discover Wi-Fi devices on network
orange device list              # Shows both USB and Wi-Fi devices
```

---

### File Transfer

Transfer files directly without creating a full backup using AFC (Apple File Conduit).

#### Browse Files on Device

```bash
# List root directory
orange files browse

# List specific directory
orange files browse /DCIM
orange files browse /DCIM/100APPLE

# Output as JSON
orange files browse /DCIM --json

# Browse with specific device
orange files browse /DCIM --udid 00008110-001234567890
```

#### Pull (Download) Files

```bash
# Pull a single file
orange files pull /DCIM/100APPLE/IMG_0001.HEIC ./photo.heic

# Pull a file to a directory
orange files pull /DCIM/100APPLE/IMG_0001.HEIC ./downloads/

# Pull an entire directory
orange files pull /DCIM/100APPLE ./all-photos

# Pull from specific device
orange files pull /DCIM/100APPLE ./photos --udid 00008110-001234567890
```

#### Pull by Category

Download all files in a category at once.

```bash
# Pull all photos and videos
orange files pull-category photos ./my-photos

# Pull music library
orange files pull-category music ./my-music

# Pull books and PDFs
orange files pull-category books ./my-books

# Pull voice memos
orange files pull-category recordings ./voice-memos

# Pull downloaded files
orange files pull-category downloads ./downloads

# Pull podcasts
orange files pull-category podcasts ./podcasts
```

#### Push (Upload) Files

```bash
# Push a single file
orange files push ./song.mp3 /iTunes_Control/Music/song.mp3

# Push a directory
orange files push ./my-music /iTunes_Control/Music

# Push to specific device
orange files push ./file.pdf /Downloads --udid 00008110-001234567890
```

#### File Information

```bash
# Get info about a file
orange files info /DCIM/100APPLE/IMG_0001.HEIC

# Get info about a directory
orange files info /DCIM

# Output as JSON
orange files info /DCIM/100APPLE/IMG_0001.HEIC --json
```

#### Category Information

```bash
# List all available categories
orange files categories

# Show only categories accessible via AFC (direct transfer)
orange files categories --afc-only

# Check size of a category before downloading
orange files size photos
orange files size music
```

#### Available Categories

| Category    | Description                      | Access |
|-------------|----------------------------------|--------|
| photos      | Camera roll photos and videos    | AFC    |
| music       | Music library                    | AFC    |
| books       | iBooks and PDFs                  | AFC    |
| downloads   | Downloaded files                 | AFC    |
| recordings  | Voice memos                      | AFC    |
| podcasts    | Downloaded podcast episodes      | AFC    |
| messages    | SMS and iMessage                 | BACKUP |
| contacts    | Address book                     | BACKUP |
| calendar    | Calendar events                  | BACKUP |
| notes       | Notes app content                | BACKUP |
| safari      | Bookmarks and history            | BACKUP |
| health      | Health and fitness data          | BACKUP |
| keychain    | Passwords (encrypted)            | BACKUP |
| settings    | Device settings                  | BACKUP |
| apps        | Application data                 | BACKUP |

**AFC** = Direct file access (fast, no backup required)
**BACKUP** = Requires `orange backup create` first

---

### Backup Management

Create, restore, and manage full device backups.

#### Create Backup

```bash
# Create backup (saves to default location)
orange backup create

# Create backup to specific directory
orange backup create --output ./my-backups

# Create backup of specific device
orange backup create --udid 00008110-001234567890
```

#### List Backups

```bash
# List all backups
orange backup list

# Output as JSON
orange backup list --json
```

#### Backup Information

```bash
# Show backup details
orange backup info ./backups/00008110-001234567890

# Show detailed info
orange backup info ./backups/00008110-001234567890 --all
```

#### Browse Backup Contents

```bash
# Browse all files in backup
orange backup browse ./backups/00008110-001234567890

# Browse specific domain
orange backup browse ./backups/00008110-001234567890 --domain HomeDomain
orange backup browse ./backups/00008110-001234567890 --domain CameraRollDomain

# Search for files
orange backup browse ./backups/00008110-001234567890 --filter "*.db"
```

#### Extract Files from Backup

```bash
# Extract a specific file
orange backup extract ./backups/00008110-001234567890 \
    --domain HomeDomain \
    --file "Library/SMS/sms.db" \
    --output ./extracted/

# Extract multiple files
orange backup extract ./backups/00008110-001234567890 \
    --domain HomeDomain \
    --file "Library/SMS/sms.db" \
    --file "Library/AddressBook/AddressBook.sqlitedb" \
    --output ./extracted/
```

#### Restore Backup

```bash
# Restore backup to device
orange backup restore ./backups/00008110-001234567890

# Restore to specific device
orange backup restore ./backups/00008110-001234567890 --udid 00008110-001234567890
```

#### Delete Backup

```bash
# Delete a backup
orange backup delete ./backups/00008110-001234567890

# Delete with confirmation skip
orange backup delete ./backups/00008110-001234567890 --yes
```

---

### Coming Soon (Phases 4-6)

```bash
# Export messages to PDF
orange export messages ./backup --format pdf --output messages.pdf

# Export contacts to CSV
orange export contacts ./backup --format csv --output contacts.csv

# Format conversion
orange convert ./photo.heic --format jpeg --output ./photo.jpg
orange convert ./song.flac --format alac --output ./song.m4a
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

## Acknowledgments

- [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) - Pure Python iOS device protocols
- [libimobiledevice](https://libimobiledevice.org/) - The foundational open-source iOS library
- [The iPhone Wiki](https://www.theiphonewiki.com/) - Protocol documentation

---

*Orange is not affiliated with Apple Inc. iPhone, iPad, and iOS are trademarks of Apple Inc.*
