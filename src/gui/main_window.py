from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QInputDialog,
    QLineEdit,
    QMainWindow,
    QMessageBox,
)

import idevice
from device_models import resolve_model_name
from ui.ui_mainwindow import Ui_MainWindow

from .async_worker import AsyncWorker

## Cartella di default per i backup locali. In futuro andra' sostituita da un
## valore letto/scritto tramite platformdirs + Preferences (vedi TODO in fondo).
DEFAULT_BACKUP_DIR = Path.home() / ".local" / "share" / "noot" / "backups"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        self.current_device_udid: str | None = None
        
        self._threadpool = QThreadPool()
        self._threadpool.setMaxThreadCount(1)
        
        self.ui.bootStatusLabel.setVisible(False) # Nascondo la label di stato bootloader/DFU finche' non viene implementata la gestione di questi stati.

        self.setupActions()
        self.setupButton()
        self.setupSignals()
        self.setupLabels()

        self.check_usbdmux()
        self.refresh_devices()
        
    def setupActions(self):
        #File
        self.ui.actionExit.triggered.connect(self.close)
        
        #Devices
        self.ui.actionRefresh_Devices.triggered.connect(self.refresh_devices)
        
        #Help
        self.ui.actionAbout_Noot.triggered.connect(self.__on_about_noot)
        self.ui.actionGitHub_Repository.triggered.connect(self.__on_github_repository)
        self.ui.actionWiki.triggered.connect(self.__on_wiki)
        self.ui.actionHow_to_Enter_DFU_mode.triggered.connect(self.__on_how_to_enter_dfu_mode)
    
    def setupButton(self):
        pass
    
    def setupSignals(self):
        pass
    
    def setupLabels(self):
        self.ui.latest_backup_label.setText("Latest Backup: Not Implemented Yet")
        if self.current_device_udid is not None:
            self.ui.enableEncrypyionButton.setText("Enable Encryption" if idevice.is_backup_encrypted(self.current_device_udid) else "Disable Encryption")
        
    ############################
    # Help Menu Actions       #
    ############################
    
    def __on_about_noot(self):
        QMessageBox.about(
            self,
            "About Noot",
            "Noot (Non-apple Open-source Operator for iTunes)"
            "iPhone backup manager for Linux, built using pymobiledevice3 module.\n\n"
            "Version: 1.0.0\n"
            "Author: SamuGallo-06\n"
            "License: LGPLv3\n"
        )

    def __on_github_repository(self):
        import webbrowser
        webbrowser.open("https://github.com/SamuGallo-06/noot")
        
    def __on_wiki(self):
        import webbrowser
        webbrowser.open("https://github.com/SamuGallo-06/noot/wiki")
        
    def __on_how_to_enter_dfu_mode(self):
        pass

    ##############################
    #  Device Summary Page       #
    ##############################

    def refresh_devices(self) -> None:
        worker = AsyncWorker(idevice.get_connected_devices)
        worker.signals.finished.connect(self.__on_devices_found)
        worker.signals.error.connect(lambda exc: print("Errore:", exc))
        self._threadpool.start(worker)
        
    def check_usbdmux(self) -> None:
        worker = AsyncWorker(idevice.check_usbmuxd)
        worker.signals.finished.connect(self.__on_usbdmux_checked)
        worker.signals.error.connect(lambda exc: print("Errore:", exc))
        self._threadpool.start(worker)
        
    def __on_usbdmux_checked(self, is_running: bool) -> None:
        if not is_running:
            QMessageBox.critical(
                self,
                "usbmuxd Not Running",
                "The usbmuxd service is not running. Please start it and try again.",
            )
        
        self.ui.usbmuxd_status_label.setText("usbmuxd is running" if is_running else "usbmuxd is NOT running")

    def _load_device_summary(self, udid: str) -> None:
        worker = AsyncWorker(idevice.get_device_summary, udid=udid)
        worker.signals.finished.connect(self.__on_summary_loaded)
        worker.signals.error.connect(lambda exc: print("Errore summary:", exc))
        self._threadpool.start(worker)

    def __on_summary_loaded(self, summary: dict) -> None:
        model = resolve_model_name(summary.get("modello"))
        name = summary.get("nome") or "Unnamed device"
        self.ui.deviceDetailsLabel.setText(f"### {model}\n{name}")
        self.ui.deviceInfoLabel.setText(f"""- **Device Name:** {name}  
         **Hardware:** {summary.get("hardware")}  
         **iOS Version:** {summary.get("ios_version")}  
         **Build:** {summary.get("build")}  
         **Serial:** {summary.get("serial")}  
         **UDID:** `{summary.get("udid")}`  
         **Storage:** {summary.get("storage_libero_gb")}/{summary.get("storage_totale_gb")} GB  
         **WiFi MAC:** `{summary.get("wifi_mac")}`  
         **Bluetooth MAC:** `{summary.get("bluetooth_mac")}`  
        """)
        
    def __on_devices_found(self, devices: list[dict]) -> None:
        if not devices:
            self.current_device_udid = None
            self.ui.deviceInfoLabel.setText("No connected devices found.")
            self.ui.deviceDetailsLabel.setText("")
            return

        if(len(devices) == 1):
            self.current_device_udid = devices[0]["udid"]
            if self.current_device_udid is not None:
                self._load_device_summary(self.current_device_udid)
                
        elif(len(devices) > 1):
            QMessageBox.critical(
                self,
                "Multiple Devices Detected",
                "Noot only supports one connected device at a time to prevent data loss or connection errors. Please disconnect all other devices and keep only the one you want to manage."
            )
            self.current_device_udid = None
            self.ui.deviceInfoLabel.setText("No connected devices found.")
            self.ui.deviceDetailsLabel.setText("")
            
            
    #############################
    # Backup Page               #
    #############################
    
    def __changeEncryptionPassword(self):
        #Called when self.ui.changeEncryptionpasswordButton is clicked
        worker = AsyncWorker(idevice.change_backup_encryption_password, udid=self.current_device_udid)
        worker.signals.finished.connect(self.__on_changeEncryptionPassword_finished)
        worker.signals.error.connect(self.__on_changeEncryptionPassword_failed)
        self._threadpool.start(worker)
        
    def __on_changeEncryptionPassword_finished(self, result):
        QMessageBox.information(
            self,
            "Change Encryption Password",
            "The backup encryption password has been changed successfully."
        )
    
    def __on_changeEncryptionPassword_failed(self, error):
        QMessageBox.critical(
            self,
            "Change Encryption Password",
            f"An error occurred while changing the backup encryption password: {error}"
        )
    
    def __enable_or_disable_Encryption(self):
        # Called when self.ui.changeEncryptionpasswordButton is clicked
        # Check if the device is currently encrypted or not
        
        if self.current_device_udid is not None:
            is_encrypted = idevice.is_backup_encrypted(self.current_device_udid)
            if(is_encrypted):
                #TODO: Implement disable encryption
                pass
            else:
                #TODO: Implement enable encryption
                pass
                

            
    def __on_enable_or_disable_Encryption_finished(self, result):
        QMessageBox.information(
            self,
            "Change Encryption Password",
            "The backup encryption password has been changed successfully."
        )
        
    def __on_enable_or_disable_Encryption_failed(self, error):
        QMessageBox.critical(
            self,
            "Change Encryption Password",
            f"An error occurred while changing the backup encryption password: {error}"
        )
    
    def __perform_backup(self):
        pass