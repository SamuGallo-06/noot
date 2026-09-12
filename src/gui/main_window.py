from __future__ import annotations

from datetime import datetime
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
        self._local_backups: list[dict[str, str | datetime | None]] = []
        
        self._threadpool = QThreadPool()
        self._threadpool.setMaxThreadCount(1)
        
        self.ui.bootStatusLabel.setVisible(False) # Nascondo la label di stato bootloader/DFU finche' non viene implementata la gestione di questi stati.
        self.ui.progressBar.setVisible(False)
        self.ui.progressLabel.setVisible(False)
        self.ui.different_device_warning.setVisible(False)
        self.ui.statusbar.showMessage("Ready")
        self.ui.tabWidget.setCurrentIndex(0)
        
        self.setupActions()
        self.setupButton()
        self.setupSignals()
        self.setupLabels()

        self.__list_backups(backup_dir=DEFAULT_BACKUP_DIR)

        self.check_usbdmux()
        self.refresh_devices()
        
    def setupActions(self):
        #File
        self.ui.actionExit.triggered.connect(self.close)
        
        #Devices
        self.ui.actionRefresh_Devices.triggered.connect(self.refresh_devices)
        self.ui.actionStart_usbmuxd.triggered.connect(self.check_usbdmux)
        
        #Help
        self.ui.actionAbout_Noot.triggered.connect(self.__on_about_noot)
        self.ui.actionGitHub_Repository.triggered.connect(self.__on_github_repository)
        self.ui.actionWiki.triggered.connect(self.__on_wiki)
        self.ui.actionHow_to_Enter_DFU_mode.triggered.connect(self.__on_how_to_enter_dfu_mode)
    
    def setupButton(self):
        # Backup Page
        self.ui.enableEncrypyionButton.clicked.connect(self.__enable_or_disable_Encryption)
        self.ui.changeEncryptionpasswordButton.clicked.connect(self.__changeEncryptionPassword)
        self.ui.performBackupButton.clicked.connect(self.__perform_backup)
        
        # Restore Page
        self.ui.deleteBackupButton.clicked.connect(self.__on_delete_backup)
        self.ui.refreshBackupsButton.clicked.connect(lambda: self.__list_backups(backup_dir=DEFAULT_BACKUP_DIR))
        self.ui.startRestoreButton.clicked.connect(self.__perform_restore)
    
    def setupSignals(self):
        self.ui.local_backup_comboBox.currentIndexChanged.connect(
            self.__on_backup_selected
        )
    
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
            #first of all, try to start usbmuxd automatically
            try:
                worker = AsyncWorker(idevice.ensure_usbmuxd_running, gui=True)
                worker.signals.finished.connect(self.__on_usbdmux_checked)
                worker.signals.error.connect(lambda exc: self.__on_usbdmux_check_failed(exc))
                self._threadpool.start(worker)
            except Exception as e:
                self.__on_usbdmux_check_failed(e)
        
        self.ui.usbmuxd_status_label.setText("usbmuxd is running" if is_running else "usbmuxd is NOT running")
    
    def __on_usbdmux_check_failed(self, error):
        QMessageBox.critical(
            self,
            "usbmuxd Not Running",
            "Cound not start usbmuxd automatically. Please start it manually and try again.\n\nError: " + str(error),
        )

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
        
        
    ##############################
    # Restore Page:              #
    ##############################
    
    def __list_backups(self, backup_dir: Path = DEFAULT_BACKUP_DIR) -> None:
        """Restituisce una lista di backup disponibili nella cartella di backup predefinita."""
        worker = AsyncWorker(idevice.list_local_backups, backup_dir=backup_dir)
        worker.signals.finished.connect(self.__on_backups_listed)
        worker.signals.error.connect(lambda exc: print("Errore:", exc))
        self._threadpool.start(worker)
    
    def __on_backups_listed(self, backups: list[dict[str, str | datetime | None]]) -> None:
        self._local_backups = backups
        self.ui.local_backup_comboBox.clear()

        if not backups:
            self.ui.local_backup_comboBox.addItem("No local backups found")
            self.ui.local_backup_comboBox.setEnabled(False)
            self.ui.backup_details_label.setText("No valid local backups found.")
            return

        self.ui.local_backup_comboBox.setEnabled(True)
        for backup in backups:
            device_name = backup.get("device_name") or "Unnamed device"
            backup_date = backup.get("backup_date")
            date_text = (
                backup_date.strftime("%Y-%m-%d %H:%M:%S")
                if isinstance(backup_date, datetime)
                else str(backup_date or "Unknown date")
            )
            self.ui.local_backup_comboBox.addItem(
                f"{device_name} - {date_text}",
                backup.get("udid"),
            )

        self.__on_backup_selected(self.ui.local_backup_comboBox.currentIndex())

    def __on_backup_selected(self, index: int) -> None:
        if index < 0:
            self.ui.backup_details_label.clear()
            return

        udid = self.ui.local_backup_comboBox.itemData(index)
        if not udid:
            self.ui.backup_details_label.clear()
            return

        backup = next(
            (
                item
                for item in self._local_backups
                if item.get("udid") == udid
            ),
            None,
        )
        if backup is None:
            self.ui.backup_details_label.clear()
            return

        backup_date = backup.get("backup_date")
        date_text = (
            backup_date.strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(backup_date, datetime)
            else str(backup_date or "Unknown date")
        )
        self.ui.backup_details_label.setText(
            f"<b>BACKUP DATE:</b> {date_text}<br>"
            f"<b>DEVICE:</b> {backup.get('device_name') or 'Unnamed device'}<br>"
            f"<b>UDID:</b> {udid}"
        )
        
        if(backup.get("udid") != self.current_device_udid):
            self.ui.different_device_warning.setVisible(True)
        else:
            self.ui.different_device_warning.setVisible(False)
            
    def __on_delete_backup(self):
        index = self.ui.local_backup_comboBox.currentIndex()
        if index < 0:
            return

        udid = self.ui.local_backup_comboBox.itemData(index)
        if not udid:
            return

        backup = next(
            (
                item
                for item in self._local_backups
                if item.get("udid") == udid
            ),
            None,
        )
        if backup is None:
            return

        confirm = QMessageBox.question(
            self,
            "Delete Backup",
            f"Are you sure you want to delete the backup for device '{backup.get('device_name') or 'Unnamed device'}' dated '{backup.get('backup_date')}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.ui.deleteBackupButton.setEnabled(False)

        worker = AsyncWorker(
            idevice.delete_local_backup,
            backup_dir=DEFAULT_BACKUP_DIR,
            udid=udid,
        )
        worker.signals.finished.connect(self.__on_backup_deleted)
        worker.signals.error.connect(self.__on_backup_delete_failed)
        self._threadpool.start(worker)

    def __on_backup_deleted(self, result) -> None:
        self.ui.deleteBackupButton.setEnabled(True)
        self.ui.statusbar.showMessage("Backup deleted successfully.", 5000)
        self.__list_backups()

    def __on_backup_delete_failed(self, error) -> None:
        self.ui.deleteBackupButton.setEnabled(True)
        QMessageBox.critical(
            self,
            "Delete Backup Failed",
            f"Could not delete the backup: {error}",
        )
        self.ui.statusbar.showMessage("Backup deletion failed.", 5000)
        
    def __perform_restore(self):
        if self.current_device_udid is None:
            QMessageBox.critical(
                self,
                "No Device Connected",
                "No device is currently connected. Please connect a device and try again.",
            )
            return

        index = self.ui.local_backup_comboBox.currentIndex()
        if index < 0:
            return

        source_udid = self.ui.local_backup_comboBox.itemData(index)
        if not source_udid:
            return

        backup = next(
            (
                item
                for item in self._local_backups
                if item.get("udid") == source_udid
            ),
            None,
        )
        if backup is None:
            return

        device_name = backup.get("device_name") or "Unnamed device"
        confirm = QMessageBox.question(
            self,
            "Restore Backup",
            f"This will overwrite all data on the connected device with the backup "
            f"for '{device_name}' dated '{backup.get('backup_date')}'. "
            f"This operation cannot be undone. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        password_dialog = EnterPasswordDialog(self)
        if password_dialog.exec() != QDialog.DialogCode.Accepted:
            return
        password = password_dialog.password()

        self.ui.progressBar.setVisible(True)
        self.ui.progressBar.setMaximum(100)
        self.ui.progressBar.setValue(0)
        self.ui.progressLabel.setVisible(True)
        self.ui.progressLabel.setText("Starting restore...")

        worker = AsyncWorker(
            idevice.run_restore,
            udid=self.current_device_udid,
            backup_dir=DEFAULT_BACKUP_DIR,
            source_udid=source_udid,
            password=password,
            restore_system_files=True,
            progress_callback=self.__on_restore_progress,
        )
        worker.signals.finished.connect(self.__on_restore_finished)
        worker.signals.error.connect(self.__on_restore_failed)
        self._threadpool.start(worker)
        
    def __on_restore_progress(self, percent: float) -> None:
        self.ui.progressBar.setValue(round(percent))
        self.ui.progressLabel.setText("Restoring...")
        
    def __on_restore_finished(self, result) -> None:
        QMessageBox.information(
            self,
            "Restore Completed",
            "The restore completed successfully."
            "Device will now reboot.",
        )
        self.ui.progressBar.setVisible(False)
        self.ui.progressLabel.setText("")
        self.ui.statusbar.showMessage("Restore completed successfully.", 5000)
        
    def __on_restore_failed(self, error) -> None:
        QMessageBox.critical(
            self,
            "Restore Failed",
            f"Could not complete the restore: {error}",
        )
        self.ui.progressBar.setVisible(False)
        self.ui.progressLabel.setText("")
        self.ui.statusbar.showMessage("Restore failed.", 5000)
            