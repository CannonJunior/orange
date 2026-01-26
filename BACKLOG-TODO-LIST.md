# Orange Project - Backlog TODO List

This file tracks tasks that have been identified but deferred for future work.

---

## Backlog Items

### 1. Populate Device Info in `orange device scan` Output

**Date Added:** 2026-01-25

**Priority:** Medium

**Description:**
The `orange device scan` command discovers Wi-Fi Sync devices and displays them in a table with columns: Device Name, Model, iOS, Address, and UDID. Currently, only "Device Name" is populated - the Model, iOS, and UDID columns show empty values ("-").

**Current Behavior:**
- Device Name: Shows the Bonjour instance name (not human-readable)
- Model: Empty
- iOS: Empty
- UDID: Empty

**Expected Behavior:**
All columns should be populated with actual device information.

**Technical Notes:**
- The `WirelessDiscovery.discover_with_info()` method is supposed to connect to each device and retrieve this info via `_get_device_info()`
- `_get_device_info()` uses `pymobiledevice3.lockdown.create_using_tcp()` to connect and get `all_values`
- The connection appears to fail silently (errors logged at debug level only)
- Bonjour `ServiceInstance.properties` dict may contain useful info but needs investigation

**Previous Attempt:**
- Attempted to fix on 2026-01-25
- Changes broke the `discover()` function entirely (no devices found)
- Had to revert changes

**Testing Requirements:**
- `orange device scan` must not produce errors
- `orange device scan` should still discover devices (even if info columns are empty)
- If device info population works, verify Model, iOS, and UDID are correctly displayed

**Files Involved:**
- `orange/core/connection/wireless.py` - `WirelessDiscovery` class, `_get_device_info()` method
- `orange/cli/commands/device.py` - `scan_cmd()` function

---

## Completed Backlog Items

### 2. Deduplicate Devices in `orange device scan` Output

**Date Added:** 2026-01-25
**Date Completed:** 2026-01-25

**Resolution:**
Deduplication implemented using `hostname|address` as unique key in `WirelessDiscovery.discover()`.
- Uses `service.host` (e.g., "iPad-mini.local") combined with first address IP
- Previous attempts failed because they used `service.instance` which was a long Bonjour identifier string
- Key insight: `service.host` contains the friendly device hostname

**Files Changed:**
- `orange/core/connection/wireless.py` - Added `seen` set for deduplication
