# PlayCover Integration Guide

Run iOS apps like Netflix on Apple Silicon Macs using PlayCover.

## Overview

Apple Silicon Macs (M1/M2/M3/M4) can run iOS apps natively because they share the same ARM architecture as iPhones and iPads. While some apps are available in the Mac App Store, many (like Netflix) block Mac availability. PlayCover allows you to sideload these apps.

## Requirements

- **Apple Silicon Mac** (M1, M2, M3, or M4 chip)
- **macOS 12.0 or later**
- **PlayCover** (free, open-source)
- **Decrypted IPA file**

## Installation

### Step 1: Install PlayCover

**Option A: Direct Download**
1. Go to [playcover.io](https://playcover.io)
2. Download the latest release
3. Move to Applications folder
4. Open (you may need to right-click → Open for first launch)

**Option B: Homebrew**
```bash
brew install --cask playcover-community
```

### Step 2: Get a Decrypted IPA

IPAs from the App Store are encrypted with FairPlay DRM and won't work with PlayCover. You need a decrypted version.

**Option A: Download Pre-Decrypted (Recommended)**

Visit [decrypt.day](https://decrypt.day) and search for your app:
- Netflix: `https://decrypt.day/app/id363590051`
- Spotify: `https://decrypt.day/app/id324684580`

**Option B: Decrypt from Jailbroken Device**

If you have a jailbroken iOS device:

```bash
# Install frida-ios-dump
pip install frida-tools
git clone https://github.com/AloneMonkey/frida-ios-dump

# List apps
python dump.py -l

# Dump (decrypt) Netflix
python dump.py com.netflix.Netflix
```

**Option C: Extract with Orange (Encrypted)**

```bash
# List installed apps
orange apps list

# Extract IPA (will be encrypted)
orange apps extract com.netflix.Netflix ./Netflix.ipa
```

> **Note:** IPAs extracted with `orange apps extract` are FairPlay encrypted and will NOT work with PlayCover unless you decrypt them using frida-ios-dump on a jailbroken device.

### Step 3: Install in PlayCover

1. Open PlayCover
2. Drag the **decrypted** IPA file into the window
3. Wait for installation to complete
4. The app icon will appear in PlayCover's library

### Step 4: Launch and Sign In

1. Click the app icon in PlayCover
2. Sign in with your Netflix account
3. Download content for offline viewing

## Netflix-Specific Notes

### Downloads Work!
The Netflix iOS app running in PlayCover supports offline downloads, just like on iPad:
- Browse content and tap the download button
- Downloads are stored locally on your Mac
- Watch offline anytime

### Downloads Don't Sync
**Important:** Downloads on your iPad do NOT sync to your Mac. You must download content separately on each device, even with the same Netflix account.

### Troubleshooting

| Issue | Solution |
|-------|----------|
| "Encrypted IPA" error | Use a decrypted IPA from decrypt.day |
| App crashes on launch | Check PlayCover GitHub issues for fixes |
| Login fails | Clear app data in PlayCover settings |
| Video won't play | Update to latest PlayCover version |
| Profile selection error | PlayCover 2.0+ includes fixes for this |

## Orange CLI Commands

### List Installed Apps
```bash
orange apps list
```

### Search for Apps
```bash
orange apps search netflix
orange apps search spotify
```

### Get App Details
```bash
orange apps info com.netflix.Netflix
```

### Extract IPA (Encrypted)
```bash
orange apps extract com.netflix.Netflix ./Netflix.ipa
```

### Show PlayCover Guide
```bash
orange apps playcover-guide
```

## Legal Considerations

| Action | Status |
|--------|--------|
| Running iOS apps on your Mac | ✅ Legal |
| Using PlayCover | ✅ Legal (open-source) |
| Jailbreaking your device | ✅ Legal in US (DMCA exemption) |
| Downloading pre-decrypted IPAs | ⚠️ Gray area |
| Decrypting IPAs yourself | ⚠️ DMCA concerns |
| Sharing decrypted IPAs | ❌ Copyright infringement |

## Workflow Summary

```
┌─────────────────────────────────────────────────────────────┐
│              Netflix on Apple Silicon Mac                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Install PlayCover                                        │
│     └── playcover.io or `brew install playcover-community`  │
│                                                              │
│  2. Get Decrypted Netflix IPA                                │
│     ├── Option A: decrypt.day (recommended)                  │
│     └── Option B: frida-ios-dump (requires jailbreak)        │
│                                                              │
│  3. Install in PlayCover                                     │
│     └── Drag IPA into PlayCover window                       │
│                                                              │
│  4. Sign In & Download                                       │
│     ├── Launch Netflix from PlayCover                        │
│     ├── Sign in with your account                            │
│     └── Download content for offline viewing                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## References

- [PlayCover Official Site](https://playcover.io)
- [PlayCover GitHub](https://github.com/PlayCover/PlayCover)
- [Decrypt IPA Store](https://decrypt.day)
- [frida-ios-dump](https://github.com/AloneMonkey/frida-ios-dump)
- [9to5Mac Guide](https://9to5mac.com/2020/11/18/how-to-install-iphone-ipad-app-m1-mac/)
