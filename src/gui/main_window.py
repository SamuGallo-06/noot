from __future__ import annotations

from pathlib import Path
from typing import Callable

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

from .enter_password_dialog import EnterPasswordDialog
from .set_password_dialog import SetPasswordDialog
from .change_password_dialog import ChangePasswordDialog

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
        self.ui.progressBar.setVisible(False)
        self.ui.progressLabel.setVisible(False)
        self.ui.statusbar.showMessage("Ready")
        self.ui.tabWidget.setCurrentIndex(0)
        
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
        self.ui.enableEncrypyionButton.clicked.connect(self.__enable_or_disable_Encryption)
        self.ui.changeEncryptionpasswordButton.clicked.connect(self.__changeEncryptionPassword)
        self.ui.performBackupButton.clicked.connect(self.__perform_backup)
    
    def setupSignals(self):
        pass
    
    def setupLabels(self):
        self.ui.latest_backup_label.setText("Latest Backup: Not Implemented Yet")
        self.ui.enableEncrypyionButton.setText("Enable Encryption")  # default finche' non si conosce lo stato reale
       
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

        if len(devices) == 1:
            self.current_device_udid = devices[0]["udid"]
            if self.current_device_udid is not None:
                self._load_device_summary(self.current_device_udid)
            self._refresh_encryption_button_state()

        elif len(devices) > 1:
            QMessageBox.critical(
                self,
                "Multiple Devices Detected",
                "Noot only supports one connected device at a time to prevent data loss or connection errors. "
                "Please disconnect all other devices and keep only the one you want to manage."
            )
            self.current_device_udid = None
            self.ui.deviceInfoLabel.setText("No connected devices found.")
            self.ui.deviceDetailsLabel.setText("")
                
            
    #############################
    # Backup Page: Encryption   #
    #############################

    def _check_backup_encryption(
        self,
        on_finished: Callable[[bool], None],
    ) -> None:
        """Legge in modo asincrono lo stato di cifratura del backup."""
        if self.current_device_udid is None:
            return

        worker = AsyncWorker(
            idevice.is_backup_encrypted,
            udid=self.current_device_udid,
        )
        worker.signals.finished.connect(on_finished)
        worker.signals.error.connect(self.__on_encryption_state_check_failed)
        self._threadpool.start(worker)
    
    def _refresh_encryption_button_state(self) -> None:
        """Aggiorna il testo del pulsante encryption in base allo stato reale del device."""
        self._check_backup_encryption(self.__on_encryption_state_checked)
    
    def __on_encryption_state_checked(self, is_encrypted: bool) -> None:
        self.ui.enableEncrypyionButton.setText(
            "Disable Encryption" if is_encrypted else "Enable Encryption"
        )
    
    def __changeEncryptionPassword(self):
        old_password, new_password = None, None
        # Show a dialog to enter the old password
        old_password_dialog = ChangePasswordDialog(self)
        if old_password_dialog.exec() == QDialog.DialogCode.Accepted:
            old_password, new_password = old_password_dialog.password()
            worker = AsyncWorker(
                idevice.change_backup_encryption_password, 
                udid=self.current_device_udid, 
                old_password=old_password, 
                new_password=new_password
            )
            worker.signals.finished.connect(self.__on_changeEncryptionPassword_finished)
            worker.signals.error.connect(self.__on_changeEncryptionPassword_failed)
            self._threadpool.start(worker)
        
        
    def __on_changeEncryptionPassword_finished(self, result):
        QMessageBox.information(
            self,
            "Password Changed",
            "The backup encryption password has been changed successfully.",
        )
        self._refresh_encryption_button_state()
    
    def __on_changeEncryptionPassword_failed(self, error):
        QMessageBox.critical(
            self,
            "Password Change Failed",
            f"Could not change the backup encryption password: {error}",
        )
        self._refresh_encryption_button_state()
    
    def __enable_or_disable_Encryption(self):
        """Enable or disable backup encryption after checking its current state."""
        self._check_backup_encryption(self.__on_encryption_state_for_action_checked)

    def __on_encryption_state_for_action_checked(self, is_encrypted: bool):
        if self.current_device_udid is None:
            return

        dialog = EnterPasswordDialog(self) if is_encrypted else SetPasswordDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        password = dialog.password()
        operation = (
            idevice.disable_backup_encryption
            if is_encrypted
            else idevice.enable_backup_encryption
        )
        worker = AsyncWorker(
            operation,
            udid=self.current_device_udid,
            password=password,
        )
        if is_encrypted:
            worker.signals.finished.connect(self.__on_disable_encryption_finished)
            worker.signals.error.connect(self.__on_disable_encryption_failed)
        else:
            worker.signals.finished.connect(self.__on_enable_encryption_finished)
            worker.signals.error.connect(self.__on_enable_encryption_failed)
        self._threadpool.start(worker)

    def __on_encryption_state_check_failed(self, error):
        QMessageBox.critical(
            self,
            "Encryption Status Check Failed",
            f"Could not determine the backup encryption status: {error}",
        )
            
    def __on_enable_encryption_finished(self, result):
        QMessageBox.information(
            self,
            "Encryption Enabled",
            "Backup encryption has been enabled successfully.",
        )
        self._refresh_encryption_button_state()
        
    def __on_enable_encryption_failed(self, error):
        QMessageBox.critical(
            self,
            "Enabling Encryption Failed",
            f"Could not enable backup encryption: {error}",
        )
    
    def __on_disable_encryption_finished(self, result):
        QMessageBox.information(
            self,
            "Encryption Disabled",
            "Backup encryption has been disabled successfully.",
        )
        self._refresh_encryption_button_state()
            
    def __on_disable_encryption_failed(self, error):
        QMessageBox.critical(
            self,
            "Disabling Encryption Failed",
            f"Could not disable backup encryption: {error}",
        )
        
    #############################
    # Backup Page: Execution    #
    #############################
    
    def __perform_backup(self):
        if self.current_device_udid is None:
            QMessageBox.critical(
                self,
                "No Device Connected",
                "No device is currently connected. Please connect a device and try again.",
            )
            return

        self._check_backup_encryption(self.__start_backup_after_encryption_check)

    def __start_backup_after_encryption_check(self, is_encrypted: bool) -> None:
        password = ""
        if is_encrypted:
            password_dialog = EnterPasswordDialog(self)
            if password_dialog.exec() != QDialog.DialogCode.Accepted:
                return
            password = password_dialog.password()
        else:
            QMessageBox.information(
                self,
                "Backup Not Encrypted",
                "Backup encryption is not enabled for this device.\n"
                "You will be prompted to set a password for the backup.",
            )
            password_dialog = SetPasswordDialog(self)
            if password_dialog.exec() != QDialog.DialogCode.Accepted:
                return
            password = password_dialog.password()

        self.ui.progressBar.setVisible(True)
        self.ui.progressBar.setMaximum(100)
        self.ui.progressBar.setValue(0)
        self.ui.progressLabel.setVisible(True)
        self.ui.progressLabel.setText("Starting backup...")
        
        full_backup = self.ui.fullBackupCheckBox.isChecked()

        exclude = [
            selection.value
            for selection, checkbox in (
                (idevice.BackupSelection.BOOKMARKS, self.ui.excludeBookmarksCheckBox),
                (idevice.BackupSelection.CALL_HISTORY, self.ui.excludeCallHistoryCheckBox),
                (idevice.BackupSelection.SMS, self.ui.excludeSMSCheckBox),
                (idevice.BackupSelection.WHATSAPP, self.ui.excludeWhatsappCheckBox),
                (idevice.BackupSelection.MESSAGES, self.ui.excludeMessagesCheckBox),
                (idevice.BackupSelection.CONTACTS, self.ui.excludeContactsCheckBox),
            )
            if checkbox.isChecked()
        ]

        worker = AsyncWorker(
            idevice.run_backup,
            udid=self.current_device_udid,
            backup_dir=DEFAULT_BACKUP_DIR,
            full=full_backup,
            exclude=exclude,
            password=password,
            progress_callback=self.__on_backup_progress,
        )
        worker.signals.finished.connect(self.__on_backup_finished)
        worker.signals.error.connect(self.__on_backup_failed)
        self._threadpool.start(worker)

    def __on_backup_progress(self, percent: float) -> None:
        self.ui.progressBar.setValue(round(percent))
        self.ui.progressLabel.setText("Backing up...")

    def __on_backup_finished(self, result) -> None:
        QMessageBox.information(
            self,
            "Backup Completed",
            "The backup completed successfully.",
        )
        self.ui.progressBar.setVisible(False)
        self.ui.progressLabel.setText("")
        self.ui.statusbar.showMessage("Backup completed successfully.", 5000)

    def __on_backup_failed(self, error) -> None:
        QMessageBox.critical(
            self,
            "Backup Failed",
            f"Could not complete the backup: {error}",
        )
        self.ui.progressBar.setVisible(False)
        self.ui.progressLabel.setText("")
        self.ui.statusbar.showMessage("Backup failed.", 5000)