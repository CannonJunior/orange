# Orange Project Context

## Project Overview

**Orange** is an open-source, cross-platform iOS file transfer and data management platform that supports transferring messages, music, files, and data between iPhone/iPad and Mac, PC, or Linux systems.

## Goals

1. **Cross-Platform Support:** Work on macOS, Windows, and Linux (competitors don't support Linux)
2. **Modular Architecture:** Reusable components for different applications
3. **Open Source:** Community-driven development
4. **No Jailbreak Required:** Use official protocols where possible
5. **Privacy First:** Local-only processing, no cloud dependencies

## Architecture

### Core Modules

```
orange/
├── core/
│   ├── connection/     # Device detection, pairing, connectivity
│   ├── backup/         # Backup creation, decryption, restore
│   ├── transfer/       # File transfer via AFC protocol
│   ├── data/           # Data extraction (messages, contacts, etc.)
│   ├── convert/        # Media format conversion
│   └── export/         # Export formatters (PDF, CSV, JSON)
├── cli/                # Command-line interface
├── gui/                # GUI application (future)
├── api/                # REST API (future)
└── tests/              # Test suite
```

### Technology Stack

- **Language:** Python 3.10+
- **iOS Protocol Library:** pymobiledevice3 (primary)
- **CLI Framework:** Click
- **GUI Framework:** TBD (Qt, Tkinter, or web-based)
- **Testing:** pytest
- **Packaging:** PyInstaller (cross-platform executables)

## Key Dependencies

- `pymobiledevice3` - iOS device communication
- `click` - CLI framework
- `python-dotenv` - Environment configuration
- `pycryptodome` - Backup decryption

## Constraints

1. **Port 9091:** Web services must use this port
2. **No hardcoded values:** Use configuration files
3. **File length limit:** 500 lines max per file
4. **Test coverage:** Every new feature needs tests

## Legal Considerations

- DMCA Section 1201(f) provides interoperability exemption
- No MFi licensing required for software-only tools
- Use established open-source libraries (17+ years of operation)
- Direct distribution recommended (Mac App Store sandbox too restrictive)

## References

- Literature Review: `docs/literature-review-ios-emulation.md`
- Task Tracking: `TASK.md`
- Project Guidelines: `CLAUDE.md`
