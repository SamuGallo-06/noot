#!/bin/bash

echo "Uninstalling NOOT..."

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (e.g., using sudo)"
    exit 1
fi

if [ -f /usr/local/bin/noot ]; then
    rm /usr/local/bin/noot
    echo "Removed /usr/local/bin/noot"
fi

if [ -d /opt/noot ]; then
    rm -rf /opt/noot
    echo "Removed /opt/noot"
fi

echo "NOOT has been uninstalled."
echo "Note: usbmuxd and libusb-1.0-0 were left installed, as they may be used by other applications."
echo "To remove them manually: sudo apt-get remove usbmuxd libusb-1.0-0"