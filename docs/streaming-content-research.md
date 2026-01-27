# Streaming Content Playback Research

**Date:** January 26, 2026
**Objective:** Investigate playing Netflix/streaming content downloaded to iPad on Linux
**Status:** Research Complete - Significant Technical & Legal Barriers Identified

---

## Executive Summary

Playing DRM-protected streaming content (Netflix, etc.) downloaded to an iOS device on a Linux machine faces **fundamental technical barriers** that cannot be overcome without circumventing copy protection mechanisms, which raises legal concerns under laws like the DMCA.

**Bottom Line:** This feature is not technically feasible through legitimate means.

---

## Technical Findings

### 1. Netflix DRM Protection

Netflix uses **Apple FairPlay DRM** on iOS devices:

| Aspect | Details |
|--------|---------|
| Encryption | AES-128 CBCS encryption via HLS |
| Key Storage | Apple Secure Enclave (hardware-level) |
| Decryption | Performed entirely in hardware, integrated into iOS/tvOS |
| Protection | Prevents screen recording, screenshots, and decoding |

**Source:** [VDOCipher - Netflix DRM](https://www.vdocipher.com/blog/2022/05/netflix-drm/)

### 2. Content Storage Location

Netflix downloaded content is stored in the app's sandboxed container:

```
/private/var/mobile/Containers/Data/Application/[Netflix-UUID]/
```

**Access Methods:**
- **AFC (Apple File Conduit):** Cannot access app containers (media partition only)
- **Backup Extraction:** Can access app data, but files are encrypted with FairPlay
- **Jailbreak:** Required for direct filesystem access, still leaves content encrypted

**Source:** [Digital Forensics Blog - iOS Data Extraction](https://blog.digital-forensics.it/2025/09/exploring-data-extraction-from-ios.html)

### 3. AirPlay Mirroring Limitations

**UxPlay** (open-source AirPlay receiver for Linux) exists but:

> "Video content encrypted by DRM (i.e. stuff in the Apple TV app, Amazon Prime, and other streaming services) isn't supported. Instead of your favourite show or movie you'll see a black screen."

**Source:** [UxPlay GitHub](https://github.com/antimof/UxPlay)

Netflix explicitly blocks AirPlay:
- Removed official AirPlay support
- Treats screen mirroring as "unauthorized recording"
- Blocks video feed while allowing audio to pass through

**Source:** [StreamFab - Netflix AirPlay Guide](https://streamfab.dvdfab.cn/blog/can-you-airplay-netflix.htm)

### 4. iOS 16+ HDMI/Display Restrictions

Apple tightened DRM enforcement in iOS 16:
- HDMI adapters now show black screen for DRM content
- AirPlay to older Apple TV models blocked for DRM content
- Hardware-level HDCP enforcement

**Source:** [9to5Mac - iOS 16 DRM Changes](https://9to5mac.com/2023/01/04/ios-16-break-drm-content-hdmi/)

### 5. pymobiledevice3 Capabilities

Current pymobiledevice3 capabilities:
- **Screenshots:** Single frame capture (requires Developer Mode)
- **Screen Mirroring:** Not supported
- **Video Streaming:** Not supported

iOS 18's iPhone Mirroring uses proprietary protocols not yet reverse-engineered.

**Source:** [pymobiledevice3 Discussion #1216](https://github.com/doronz88/pymobiledevice3/discussions/1216)

---

## Approaches Evaluated

### Approach 1: Extract Downloaded Files via AFC
**Status:** ❌ Not Possible
- AFC only accesses `/var/mobile/Media/` (media partition)
- App containers are not accessible via AFC
- Even if accessed, files are FairPlay encrypted

### Approach 2: Extract via Backup
**Status:** ❌ Not Useful
- Backup can include app data (encrypted backup)
- Downloaded video files are still FairPlay encrypted
- Cannot decrypt without Apple's Secure Enclave

### Approach 3: AirPlay Screen Mirroring
**Status:** ❌ Blocked by DRM
- UxPlay works for non-DRM content
- Netflix/streaming apps show black screen
- Apple enforces at iOS level

### Approach 4: HDMI Capture Card
**Status:** ❌ Blocked by HDCP
- iOS enforces HDCP for DRM content
- Requires HDCP-stripping hardware (legally questionable)
- iOS 16+ tightened enforcement

### Approach 5: Screen Recording on Device
**Status:** ❌ Blocked by iOS
- iOS blocks screen recording for DRM apps
- Recording shows black rectangle over video

### Approach 6: Remote Desktop/Control
**Status:** ⚠️ Same DRM limitations apply
- Would still show black screen for DRM content
- No benefit over AirPlay approach

---

## Legal Considerations

### DMCA (Digital Millennium Copyright Act)
- Circumventing DRM protection mechanisms is illegal under DMCA Section 1201
- Even for personal use ("format shifting"), circumvention is prohibited
- Penalties include fines and criminal prosecution

### Fair Use
- Does not apply to circumvention (separate from copyright infringement)
- No "personal use" exception for DRM circumvention

### Terms of Service
- Netflix ToS explicitly prohibits:
  - Copying or downloading content beyond app functionality
  - Circumventing technical protection measures
  - Using unauthorized devices for playback

---

## Alternative Solutions (Legal)

### 1. Native Linux Netflix (Web Browser)
- Use Firefox or Chrome on Linux
- Netflix works at 720p/1080p (depending on browser/Widevine)
- Requires internet connection

### 2. Cast to Linux
- Use Chromecast-compatible receiver on Linux
- Limited to casting-enabled content

### 3. Dedicated Streaming Device
- Connect Chromecast/Fire Stick to monitor
- Use iPad as controller only

### 4. For Non-DRM Content Only
If working with **personal videos** (not streaming service content):
- **UxPlay** for AirPlay mirroring works perfectly
- **VLC Streamer** for streaming personal media
- **AFC/Backup** for transferring personal photos/videos

---

## Recommendations

### For Orange Project

1. **Do Not Implement DRM Circumvention**
   - Legal liability (DMCA)
   - Ethical concerns
   - Would not align with project goals

2. **Focus on Legitimate Use Cases**
   - Personal media transfer (photos, videos, music)
   - Non-DRM content streaming via AirPlay (document UxPlay integration)
   - Backup/restore functionality

3. **Document Limitations Clearly**
   - Add FAQ about streaming content limitations
   - Explain why this is a platform restriction, not Orange limitation

### Proposed Features (Alternative)

Instead of DRM content playback, consider:

| Feature | Description | Feasibility |
|---------|-------------|-------------|
| UxPlay Integration | Document/automate UxPlay for personal content | ✅ High |
| Personal Video Sync | Two-way sync of non-DRM videos | ✅ High |
| Photo/Video Export | Export camera roll to Linux | ✅ Already implemented |
| Music Library Sync | Sync personal music collection | ✅ Medium |

---

---

## macOS Apple Silicon: iOS App Sideloading (Updated 2026-01-26)

### Overview

Apple Silicon Macs (M1/M2/M3/M4) can run iOS apps natively due to shared ARM architecture. This provides a legitimate path to running the Netflix iOS app on macOS, though with important caveats.

### The Approach: PlayCover + Decrypted IPA

| Component | Description |
|-----------|-------------|
| **PlayCover** | Open-source tool that runs iOS apps on Apple Silicon Macs |
| **Decrypted IPA** | Netflix .ipa file without FairPlay encryption |
| **Result** | Native Netflix iOS app running on Mac with download capability |

**Source:** [MacHow2 - PlayCover Review](https://machow2.com/playcover-review/)

### Why This Works

1. **Apple Silicon = ARM architecture** - Same as iPhone/iPad
2. **iOS apps run natively** - Not emulated, actual iOS binaries
3. **PlayCover bypasses App Store restrictions** - Netflix blocked itself from Mac App Store
4. **Full app functionality** - Including offline downloads

### Critical Limitation: Downloads Don't Transfer

> "Netflix does not allow users to transfer downloaded content between devices... downloads are tied to the device from which they were downloaded."

**Source:** [FlixiCam Guide](https://www.flixicam.com/guide/watch-netflix-downloads-on-another-different-device.html)

**This means:**
- Downloads on iPad ≠ Downloads on Mac
- Each device must download content separately
- Same Netflix account, but fresh downloads required

### Workflow for Orange Project (macOS)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Netflix on Mac Workflow                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Option A: Use Third-Party Decrypted IPA                        │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ Download IPA │ -> │  PlayCover   │ -> │ Netflix App  │       │
│  │ (decrypt.day)│    │  (install)   │    │ (download)   │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│                                                                  │
│  Option B: Extract from Jailbroken Device (via Orange)          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ Jailbroken   │ -> │   Orange     │ -> │  Decrypted   │       │
│  │   Device     │    │ (extract)    │    │    IPA       │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│         │                                       │                │
│         v                                       v                │
│  ┌──────────────┐                      ┌──────────────┐         │
│  │ frida-dump   │                      │  PlayCover   │         │
│  │ (decrypt)    │                      │  (install)   │         │
│  └──────────────┘                      └──────────────┘         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### What Orange Can Provide

| Capability | Status | Notes |
|------------|--------|-------|
| List installed apps | ✅ Possible | `pymobiledevice3 apps list` |
| Extract encrypted IPA | ✅ Possible | From non-jailbroken device |
| Decrypt IPA | ❌ Requires Jailbreak | Need frida-ios-dump or bagbak |
| Install IPA to Mac | ⚠️ Out of Scope | Use PlayCover directly |
| Transfer Netflix downloads | ❌ Not Possible | DRM prevents transfer |

### Tools Required (External)

| Tool | Purpose | Source |
|------|---------|--------|
| **PlayCover** | Run iOS apps on Mac | [playcover.io](https://playcover.io) |
| **Decrypted IPA** | Netflix without DRM | [decrypt.day](https://decrypt.day) |
| **frida-ios-dump** | Decrypt from jailbroken device | [GitHub](https://github.com/AloneMonkey/frida-ios-dump) |

### Implementation Plan for Orange

**Phase 1: App Discovery & Listing**
- Add `orange apps list` command to show installed iOS apps
- Show app bundle IDs, versions, sizes
- Identify which apps can potentially be extracted

**Phase 2: IPA Extraction (Encrypted)**
- Add `orange apps extract <bundle_id>` command
- Extract IPA from device (will be FairPlay encrypted)
- Warn user that decryption requires jailbreak

**Phase 3: Documentation & Integration Guides**
- Document PlayCover setup workflow
- Document IPA decryption options
- Provide helper scripts for common workflows

### Legal Considerations

| Action | Legality |
|--------|----------|
| Running iOS apps on Mac | ✅ Legal (your own apps) |
| Using PlayCover | ✅ Legal (open-source tool) |
| Downloading decrypted IPAs | ⚠️ Gray area (circumventing DRM) |
| Decrypting IPAs yourself | ⚠️ DMCA concerns |
| Jailbreaking your device | ✅ Legal in US (DMCA exemption) |

---

## macOS-Specific Investigation (Added 2026-01-26)

### Question: Would macOS Provide Additional Capabilities?

**Answer: No. The same DRM restrictions apply on macOS.**

### macOS-Specific Features Evaluated

| Feature | Result | Details |
|---------|--------|---------|
| **iPhone Mirroring (macOS Sequoia)** | ❌ Black Screen | DRM apps show black screen, same as AirPlay |
| **AirPlay to Mac** | ❌ Blocked | Netflix disabled AirPlay support in 2019 |
| **Continuity/Handoff** | ❌ Not Applicable | Works for apps, not media playback |
| **Finder/iTunes Sync** | ❌ No Access | Netflix doesn't enable File Sharing |
| **Same Apple ID** | ❌ No Benefit | DRM still enforced per-device |
| **FairPlay APIs** | ❌ Locked | Keys only accessible to authorized apps |

### iPhone Mirroring (macOS Sequoia)

Apple's newest feature, iPhone Mirroring in macOS Sequoia, **explicitly blocks DRM content**:

> "Any app that has DRM restrictions with Apple AirPlay also won't work in iPhone Mirroring mode. This includes Netflix and Disney Plus."

**Source:** [Tom's Guide - iPhone Mirroring](https://www.tomsguide.com/computing/macos/macos-sequoia-7-things-you-need-to-know-about-iphone-mirroring)

Users report:
> "When trying to watch movies and TV shows from certain apps like Hulu and Netflix, you may encounter a blank black screen with the iPhone Mirroring app."

**Source:** [Apple Community Discussion](https://discussions.apple.com/thread/255097310)

### AirPlay to Mac

macOS Monterey+ can act as an AirPlay receiver, but:

1. **Netflix removed AirPlay support** (2019):
   > "With AirPlay support rolling out to third-party devices, there isn't a way for us to distinguish between devices... we have decided to discontinue Netflix AirPlay support."

2. **DRM content shows black screen** on all AirPlay receivers, including Macs

**Source:** [AirDroid - Netflix AirPlay Guide](https://www.airdroid.com/screen-mirror/can-you-airplay-netflix/)

### FairPlay DRM on macOS

macOS uses the same FairPlay DRM as iOS:

- Keys are tied to Apple ID and specific authorized devices
- AVFoundation handles decryption securely
- No API exposes decryption keys to applications
- Content must be played within authorized apps only

> "FairPlay Streaming is a DRM technology used to secure streaming media delivery to devices through the HTTP Live Streaming (HLS) protocol... on iOS, iPadOS, watchOS 7, tvOS, and macOS."

**Source:** [VDOCipher - FairPlay DRM](https://www.vdocipher.com/blog/fairplay-drm-ios-safari-html5/)

### Why macOS Doesn't Help

| Reason | Explanation |
|--------|-------------|
| **Same DRM System** | macOS uses identical FairPlay DRM as iOS |
| **App-Level Blocking** | Netflix app blocks mirroring/AirPlay regardless of receiver |
| **No Key Access** | Apple doesn't provide APIs to access decryption keys |
| **Hardware Enforcement** | T2/Apple Silicon chips enforce Secure Enclave protection |
| **Apple's Design** | Apple explicitly designed the system to prevent cross-device playback |

### What macOS CAN Do (Legal Alternatives)

1. **Watch Netflix in Safari** - Native Netflix playback at up to 4K HDR
2. **Use Apple TV app** - For Apple TV+ and iTunes purchases
3. **Download in Safari** - For services that allow browser downloads
4. **Personal content via AirPlay** - Non-DRM videos work perfectly

### Comparison: Linux vs macOS

| Capability | Linux | macOS |
|------------|-------|-------|
| Netflix in browser | ✅ 720p-1080p | ✅ Up to 4K HDR |
| AirPlay receiver | ✅ UxPlay (no DRM) | ✅ Built-in (no DRM) |
| iPhone Mirroring | ❌ Not available | ❌ Black screen for DRM |
| Access iOS app data | ❌ Sandboxed | ❌ Sandboxed |
| Play iOS downloads | ❌ FairPlay encrypted | ❌ FairPlay encrypted |

**Conclusion:** macOS provides no advantage for playing DRM-protected iOS content. The restrictions are enforced at the content/app level by Netflix, not by the receiving platform.

---

## Conclusion

**The requested feature (playing Netflix downloads on Linux) is not technically feasible through legitimate means.**

**The same applies to macOS** - Apple's own platform cannot play Netflix downloads from an iOS device due to Netflix's DRM policies and app-level blocking.

The DRM protection chain is enforced at multiple levels:
1. **Content Level:** FairPlay encryption on stored files
2. **OS Level:** iOS blocks screen capture/mirroring for DRM content
3. **Hardware Level:** Secure Enclave, HDCP enforcement
4. **Network Level:** Netflix blocks AirPlay

Any solution would require circumventing these protections, which is:
- Technically complex (hardware-based DRM)
- Legally problematic (DMCA)
- Against service terms

**Recommendation:** Close this task as "Won't Implement" and document the limitations in user-facing documentation.

---

## References

1. [Netflix DRM - VDOCipher](https://www.vdocipher.com/blog/2022/05/netflix-drm/)
2. [Apple FairPlay DRM](https://www.vdocipher.com/blog/fairplay-drm-ios-safari-html5/)
3. [UxPlay - AirPlay for Linux](https://github.com/antimof/UxPlay)
4. [iOS Data Extraction - Digital Forensics](https://blog.digital-forensics.it/2025/09/exploring-data-extraction-from-ios.html)
5. [Netflix AirPlay Issues](https://streamfab.dvdfab.cn/blog/can-you-airplay-netflix.htm)
6. [iOS 16 DRM Changes](https://9to5mac.com/2023/01/04/ios-16-break-drm-content-hdmi/)
7. [pymobiledevice3 Screen Mirroring Discussion](https://github.com/doronz88/pymobiledevice3/discussions/1216)
