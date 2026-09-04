<div align="center">

  <!-- Stato Avanzamento Moduli -->
  <img src="https://img.shields.io/badge/CLI-Completed-brightgreen?style=for-the-badge&logo=gnubash&logoColor=white" alt="CLI Completed" />
  <img src="https://img.shields.io/badge/GUI-In_Progress-orange?style=for-the-badge&logo=qt&logoColor=white" alt="GUI In Progress" />

  <br/>

  <!-- Stack Tecnologico -->
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3" />
  <img src="https://img.shields.io/badge/GUI-PySide6-41CD52?style=for-the-badge&logo=qt&logoColor=white" alt="PySide6" />

  <br/>

  <!-- Target & Compatibilità -->
  <img src="https://img.shields.io/badge/Platform-Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black" alt="Linux" />
  <img src="https://img.shields.io/badge/Target-iOS_Backups-000000?style=for-the-badge&logo=apple&logoColor=white" alt="iOS Backups" />

</div>

# Noot (Non-apple Open-source Operator for iTunes)

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

## Command Line

The software can be used from the command line. To see the available commands, run:

```bash
noot --help
```

```bash
(.venv) user@Some-Host:~/noot$ python3 main.py --help

 Usage: main.py [OPTIONS] COMMAND [ARGS]...

 NOOT - iOS device management and backup utility

╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --gui                         Launch GUI interface                                                              │
│ --install-completion          Install completion for the current shell.                                         │
│ --show-completion             Show completion for the current shell, to copy it or customize the installation.  │
│ --help                        Show this message and exit.                                                       │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ──────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ list                List all connected iOS devices.                                                             │
│ summary             Display detailed hardware and system info for a specific device.                            │
│ enable-encryption   Enable backup encryption on the device by setting a new backup password.                    │
│ disable-encryption  Disable backup encr![CLI Status](https://img.shields.io/badge/CLI-Completed-brightgreen)yption on the device (requires the current backup password).             │
│ backup              Run a local backup for the specified device.                                                │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

This will display a list of available commands and their usage
