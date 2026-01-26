#!/bin/bash
#
# Orange Startup Script
# Starts all required services for iOS device communication
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Orange Startup Script${NC}"
echo "========================"

# Function to check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${YELLOW}Note: Some operations may require sudo${NC}"
        return 1
    fi
    return 0
}

# Function to start usbmuxd
start_usbmuxd() {
    echo -n "Checking usbmuxd... "

    # Check if usbmuxd process is running (either via systemd or manually)
    if pgrep -x usbmuxd > /dev/null 2>&1; then
        echo -e "${GREEN}already running${NC}"
        return 0
    fi

    echo -e "${YELLOW}not running${NC}"

    # Check if we can use sudo
    if sudo -n true 2>/dev/null; then
        # Start usbmuxd directly with -f flag to prevent auto-exit
        # The -f flag keeps it in foreground but we background it
        echo -n "  Starting usbmuxd (persistent mode)... "

        # Kill any existing instance first
        sudo pkill -x usbmuxd 2>/dev/null || true
        sleep 0.5

        # Start usbmuxd without auto-exit (no --exit flag, use -f in background)
        # Using systemd but overriding to not auto-exit
        if sudo usbmuxd -v 2>/dev/null; then
            sleep 1
            if pgrep -x usbmuxd > /dev/null 2>&1; then
                echo -e "${GREEN}✓ started${NC}"
                return 0
            fi
        fi
        echo -e "${RED}✗ failed${NC}"
    fi

    # Provide manual instructions
    echo ""
    echo -e "  ${YELLOW}Please start usbmuxd manually (persistent mode):${NC}"
    echo "    sudo usbmuxd"
    echo ""
    echo "  Note: The default systemd service auto-exits when no devices are"
    echo "  connected. Running 'sudo usbmuxd' directly keeps it running for"
    echo "  Wi-Fi device access."
    echo ""
    return 1
}

# Function to check for connected iOS devices
check_devices() {
    echo -n "Checking for iOS devices... "

    # Wait a moment for device detection
    sleep 1

    # Try to list devices using pymobiledevice3
    if command -v python3 &> /dev/null; then
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        if [ -f "$SCRIPT_DIR/venv_linux/bin/python" ]; then
            DEVICE_COUNT=$("$SCRIPT_DIR/venv_linux/bin/python" -c "
from pymobiledevice3.usbmux import list_devices
try:
    devices = list_devices()
    print(len(devices))
except:
    print(0)
" 2>/dev/null)
            if [ "$DEVICE_COUNT" -gt 0 ]; then
                echo -e "${GREEN}$DEVICE_COUNT device(s) found${NC}"
            else
                echo -e "${YELLOW}no devices connected${NC}"
                echo "  Connect an iOS device via USB to continue"
            fi
        else
            echo -e "${YELLOW}skipped (venv not found)${NC}"
        fi
    else
        echo -e "${YELLOW}skipped (python3 not found)${NC}"
    fi
}

# Function to activate virtual environment
activate_venv() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    VENV_PATH="$SCRIPT_DIR/venv_linux"

    if [ -d "$VENV_PATH" ]; then
        echo -n "Virtual environment... "
        # Note: This only works if script is sourced, not executed
        if [ -n "$VIRTUAL_ENV" ]; then
            echo -e "${GREEN}already active${NC}"
        else
            echo -e "${YELLOW}available at venv_linux${NC}"
            echo "  Run: source venv_linux/bin/activate"
        fi
    else
        echo -e "${YELLOW}Virtual environment not found at $VENV_PATH${NC}"
        echo "  Run: python3 -m venv venv_linux && pip install -r requirements.txt"
    fi
}

# Function to check Wi-Fi sync status
check_wifi_sync() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    if [ -f "$SCRIPT_DIR/venv_linux/bin/python" ]; then
        echo ""
        echo -e "${YELLOW}Wi-Fi Sync Status:${NC}"

        "$SCRIPT_DIR/venv_linux/bin/python" - << 'PYTHON_SCRIPT'
from pymobiledevice3.usbmux import list_devices
from pymobiledevice3.lockdown import create_using_usbmux

try:
    devices = list_devices()
    if not devices:
        print("  No USB devices - cannot check Wi-Fi sync status")
        print("  Connect device via USB to enable Wi-Fi sync")
    else:
        for d in devices:
            try:
                lockdown = create_using_usbmux(serial=d.serial)
                wifi_enabled = lockdown.get_value(
                    key="EnableWifiConnections",
                    domain="com.apple.mobile.wireless_lockdown"
                )
                status = "ENABLED" if wifi_enabled else "DISABLED"
                print(f"  Device {d.serial[:12]}...: Wi-Fi sync {status}")

                if not wifi_enabled:
                    print(f"    Run: orange device wifi --enable")
            except Exception as e:
                print(f"  Device {d.serial[:12]}...: Could not check ({e})")
except Exception as e:
    print(f"  Could not check Wi-Fi status: {e}")
PYTHON_SCRIPT
    fi
}

# Function to show usage
show_usage() {
    echo ""
    echo -e "${GREEN}Ready to use Orange!${NC}"
    echo ""
    echo "Quick start:"
    echo "  source venv_linux/bin/activate"
    echo "  orange device list          # List USB devices"
    echo "  orange device scan          # Find Wi-Fi devices"
    echo "  orange files browse         # Browse device files"
    echo ""
    echo "Wi-Fi setup (one-time, requires USB):"
    echo "  orange device pair          # Pair with device"
    echo "  orange device wifi --enable # Enable Wi-Fi sync"
    echo ""
}

# Main execution
main() {
    echo ""

    # Start usbmuxd service
    start_usbmuxd || exit 1

    # Check for devices
    check_devices

    # Check Wi-Fi sync status if device connected
    check_wifi_sync

    # Check virtual environment
    activate_venv

    # Show usage
    show_usage
}

# Run main
main "$@"
