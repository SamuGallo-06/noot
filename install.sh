apt-get update
apt-get install -y usbmuxd libusb-1.0-0
systemctl enable --now usbmuxd
pip3 install -r requirements.txt