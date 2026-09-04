#!/bin/bash

echo "#######################################################"
echo "#                                                     #"
echo "#  NOOT - Non-apple Open-source Operator for iTunes   #"
echo "#                                                     #"
echo "#######################################################"
echo ""
# Check if the script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (e.g., using sudo)"
  exit 1
fi

echo "Installing dependencies..."
# Update package list and install dependencies
apt-get update
apt-get install -y usbmuxd libusb-1.0-0
systemctl enable --now usbmuxd
pip3 install -r requirements.txt

echo "Installing NOOT..."
mkdir -p /opt/noot
cp main.py /opt/noot
cp idevice.py /opt/noot
cp noot /usr/local/bin/noot
chmod +x /usr/local/bin/noot

echo "Installation complete. You can now run NOOT using the command 'noot'."