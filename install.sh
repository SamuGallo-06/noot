#!/bin/bash

echo "#######################################################"
echo "#                                                     #"
echo "#  NOOT - Non-apple Open-source Operator for iTunes   #"
echo "#                                                     #"
echo "#######################################################"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (e.g., using sudo)"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing system dependencies..."
apt-get update
apt-get install -y usbmuxd libusb-1.0-0
systemctl enable --now usbmuxd

echo "Installing NOOT..."
mkdir -p /opt/noot
cp -r "$SCRIPT_DIR/dist/Noot/." /opt/noot/
chmod +x /opt/noot/Noot

cp "$SCRIPT_DIR/noot" /usr/local/bin/noot
chmod +x /usr/local/bin/noot

echo "Installation complete. You can now run NOOT using the command 'noot'."