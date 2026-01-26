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

    if systemctl is-active --quiet usbmuxd 2>/dev/null; then
        echo -e "${GREEN}already running${NC}"
        return 0
    fi

    echo -e "${YELLOW}not running${NC}"

    # Check if we can use sudo
    if sudo -n true 2>/dev/null; then
        # Can sudo without password
        echo -n "  Starting usbmuxd... "
        if sudo systemctl start usbmuxd 2>/dev/null; then
            sleep 1
            if systemctl is-active --quiet usbmuxd; then
                echo -e "${GREEN}✓ started${NC}"
                return 0
            fi
        fi
        echo -e "${RED}✗ failed${NC}"
    fi

    # Provide manual instructions
    echo ""
    echo -e "  ${YELLOW}Please start usbmuxd manually:${NC}"
    echo "    sudo systemctl start usbmuxd"
    echo ""
    echo "  Or run usbmuxd in foreground for debugging:"
    echo "    sudo usbmuxd -f -v"
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

# Function to show usage
show_usage() {
    echo ""
    echo -e "${GREEN}Ready to use Orange!${NC}"
    echo ""
    echo "Quick start:"
    echo "  source venv_linux/bin/activate"
    echo "  orange device list"
    echo "  orange files browse"
    echo "  orange files categories"
    echo ""
}

# Main execution
main() {
    echo ""

    # Start usbmuxd service
    start_usbmuxd || exit 1

    # Check for devices
    check_devices

    # Check virtual environment
    activate_venv

    # Show usage
    show_usage
}

# Run main
main "$@"
