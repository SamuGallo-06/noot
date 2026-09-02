# Noot

iPhone backup manager for Linux, built using pymobiledevice3 module.

## Requirements

- Python 3.6+
- pymobiledevice3 module (install with `pip install pymobiledevice3`)
- libusb-1.0-0
- usbmuxd

## Installation

First of all, you need to install the required dependencies.

### Debian based distributions

You can do this by running the provided `install.sh` script:

```bash
chmod +x install.sh
sudo ./install.sh
```

The script will install the required dependencies and pyhton modules, and enable the usbmuxd service.

### Arch based distributions

You can install the required dependencies using pacman:

```bash
sudo pacman -S python-pip libusb usbmuxd
systemctl enable --now usbmuxd
```

## Command Line Usage

### Scriptable Mode

The software can be used from the command line. To see the available commands, run:

```bash
python3 main.py --help
```

This will display a list of available commands and their usage

### Interactive Mode

You can also run the software in interactive mode by running:

```bash
python3 main.py
```

without any arguments. This will start an interactive shell where you can run commands.
