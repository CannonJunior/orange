# Orange

**Cross-platform iOS file transfer and data management for Mac, Windows, and Linux.**

Orange is an open-source tool for transferring messages, music, files, and data between iPhone/iPad and your computer - without iTunes or iCloud.

## Features (Planned)

- **Device Connection** - USB and Wi-Fi device detection with secure pairing
- **Full Backup & Restore** - Create and restore encrypted iOS backups
- **File Transfer** - Bidirectional transfer of photos, videos, music, and documents
- **Data Export** - Extract messages, contacts, calendar, and notes to PDF/CSV/JSON
- **Format Conversion** - Convert FLAC to ALAC, HEIC to JPEG, and more
- **Cross-Platform** - Works on macOS, Windows, and Linux

## Status

**Current Phase:** Planning & Research

- [x] Literature Review - Completed
- [x] Implementation Plan - Completed
- [ ] Phase 1: Connection Module - In Progress
- [ ] Phase 2: Backup Engine
- [ ] Phase 3: File Transfer
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

```bash
# List connected iOS devices
orange device list

# Show device information
orange device info <udid>

# Pair with a device
orange device pair <udid>

# Create a backup
orange backup create <udid> --output ./backups

# Export messages to PDF
orange export messages <backup-id> --format pdf --output messages.pdf
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
