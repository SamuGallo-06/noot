apt-get update
apt-get install -y python3-pip python3-venv usbmuxd libusb-1.0-0
systemctl enable --now usbmuxd
pip install -r requirements.txt