from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QInputDialog,
    QLineEdit,
    QMainWindow,
    QMessageBox,
)

import idevice
from idevice import IdevicerestoreNotInstalledError, IdevicerestoreError, IdevicerestoreCancelledError
from device_models import resolve_model_name
from settings import get_ask_udid_confirmation, get_backup_directory
from ui.ui_mainwindow import Ui_MainWindow
from .preferences_form import PreferencesDialog

from .enter_password_dialog import EnterPasswordDialog
from .set_password_dialog import SetPasswordDialog
from .change_password_dialog import ChangePasswordDialog

from .async_worker import AsyncWorker
import settings

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        """@brief Initialize the main application window and its workers."""
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        self.current_device_udid: str | None = None
        self._local_backups: list[dict[str, str | datetime | None]] = []
        self._active_workers: set[AsyncWorker] = set()
        self._busy: bool = False
        
        self._threadpool = QThreadPool()
        self._threadpool.setMaxThreadCount(1)  # Limit the number of concurrent threads to avoid overwhelming the system
        
        self.ui.bootStatusLabel.setVisible(False) # Nascondo la label di stato bootloader/DFU finche' non viene implementata la gestione di questi stati.
        self.ui.progressBar.setVisible(False)
        self.ui.progressLabel.setVisible(False)
        self.ui.different_device_warning.setVisible(False)
        self.ui.statusbar.showMessage(self.tr("Ready"))
        self.ui.tabWidget.setCurrentIndex(0)
        
        self.setupActions()
        self.setupButton()
        self.setupSignals()
        self.setupLabels()

        self.__list_backups(backup_dir=get_backup_directory())

        self.check_usbdmux()
        self.refresh_devices()

    
    def apply_theme(self, theme: str) -> None:
            """theme: 'light', 'dark', o 'system'"""
            hints = QGuiApplication.styleHints()
            if theme == "light":
                hints.setColorScheme(Qt.ColorScheme.Light)
            elif theme == "dark":
                hints.setColorScheme(Qt.ColorScheme.Dark)
            else:  # system
                hints.setColorScheme(Qt.ColorScheme.Unknown)  # Unknown = segui il sistema
        
    def setupActions(self):
        """@brief Connect menu actions to their handlers."""
        #File
        self.ui.actionPreferences.triggered.connect(self.__on_preferences)
        self.ui.actionExit.triggered.connect(self.close)
        
        #Devices
        self.ui.actionRefresh_Devices.triggered.connect(self.refresh_devices)
        self.ui.actionStart_usbmuxd.triggered.connect(self.check_usbdmux)
        #--
        self.ui.actionShutdown.triggered.connect(self.__on_shutdown)
        self.ui.actionReboot.triggered.connect(self.__on_reboot)
        
        #Help
        self.ui.actionAbout_Noot.triggered.connect(self.__on_about_noot)
        self.ui.actionGitHub_Repository.triggered.connect(self.__on_github_repository)
        self.ui.actionWiki.triggered.connect(self.__on_wiki)
        self.ui.actionHow_to_Enter_DFU_mode.triggered.connect(self.__on_how_to_enter_dfu_mode)
    
    def setupButton(self):
        """@brief Connect button signals to their handlers."""
        # Backup Page
        self.ui.enableEncrypyionButton.clicked.connect(self.__enable_or_disable_Encryption)
        self.ui.changeEncryptionpasswordButton.clicked.connect(self.__changeEncryptionPassword)
        self.ui.performBackupButton.clicked.connect(self.__perform_backup)
        
        # Restore Page
        self.ui.deleteBackupButton.clicked.connect(self.__on_delete_backup)
        self.ui.refreshBackupsButton.clicked.connect(lambda: self.__list_backups(backup_dir=get_backup_directory()))
        self.ui.startRestoreButton.clicked.connect(self.__perform_restore)
        
        #iOS Version Page
        self.ui.browseIpswFileButton.clicked.connect(self.__on_browse_ipsw)
        self.ui.flashFirmwareButton.clicked.connect(self.__on_flash_ipsw)
        
        #Danger Zone Page
        self.ui.eraseDeviceButton.clicked.connect(self.__on_factory_reset)
        self.ui.recoveryModeButton.clicked.connect(self.__on_reboot_recovery)
    
    def setupSignals(self):
        """@brief Connect non-button widget signals."""
        self.ui.local_backup_comboBox.currentIndexChanged.connect(
            self.__on_backup_selected
        )
    
    def setupLabels(self):
        """@brief Initialize labels whose content depends on runtime state."""
        self.ui.latest_backup_label.setText(self.tr("Latest Backup: Not Implemented Yet"))
        self.ui.enableEncrypyionButton.setText(self.tr("Enable Encryption"))  # default, will be updated after checking the device state
        
    def _set_busy(self, busy: bool) -> None:
        """@brief Enable or disable controls during an asynchronous operation.

        With QThreadPool at 1 thread, operations would still be queued
        instead of executed in parallel, but queuing a backup/restore/flash
        without the user noticing is still confusing behavior
        (e.g. a second click on "Perform Backup" would silently start only
        at the end of the first). Disabling controls makes it explicit that there's already
        an operation in progress.

        self._busy also lets other code paths (e.g. refresh_devices) check
        whether a long-running operation is in flight without depending on
        the enabled state of any particular widget.

        @param busy Whether controls should be disabled.
        """
        self._busy = busy
        self.ui.performBackupButton.setEnabled(not busy)
        self.ui.startRestoreButton.setEnabled(not busy)
        self.ui.flashFirmwareButton.setEnabled(not busy)
        self.ui.eraseDeviceButton.setEnabled(not busy)
        self.ui.enableEncrypyionButton.setEnabled(not busy)
        self.ui.changeEncryptionpasswordButton.setEnabled(not busy)
        self.ui.deleteBackupButton.setEnabled(not busy)
        self.ui.actionRefresh_Devices.setEnabled(not busy)
        
    #########################
    # File Menu Actions     #
    #########################
    
    def __on_preferences(self):
        """@brief Show the preferences dialog."""
        form = PreferencesDialog(self)
        form.exec()
       
    ############################
    # Help Menu Actions       #
    ############################
    
    def __on_about_noot(self):
        """@brief Show the application information dialog."""
        QMessageBox.about(
            self,
            self.tr("About Noot"),
            self.tr("Noot (Non-apple Open-source Operator for iTunes)\n iPhone backup manager for Linux, built using pymobiledevice3 module.\n\n"
            "Version: 1.1.0\n"
            "Author: SamuGallo-06\n"
            "License: LGPLv3\n")
        )

    def __on_github_repository(self):
        """@brief Open the project's GitHub repository in a web browser."""
        import webbrowser
        webbrowser.open("https://github.com/SamuGallo-06/noot")
        
    def __on_wiki(self):
        """@brief Open the project's wiki in a web browser."""
        import webbrowser
        webbrowser.open("https://github.com/SamuGallo-06/noot/wiki")
        
    def __on_how_to_enter_dfu_mode(self):
        """@brief Show instructions for entering DFU mode."""
        pass
    
    def _run_worker(self, worker: AsyncWorker) -> None:
            """@brief Start an AsyncWorker while keeping a strong reference to it.

            QThreadPool.start() hands the QRunnable to the C++ pool, but does not
            prevent Python's garbage collector from collecting the worker object
            (and its signals, a child QObject) if no Python variable still
            references it when garbage collection runs. This can happen before
            the pool thread has actually executed run(). The symptom is a worker
            that never emits either finished or error, without any visible
            exception. Keeping a reference in self._active_workers until it
            finishes resolves the problem.

            @param worker Worker to retain and start.
            """
            self._active_workers.add(worker)

            def _cleanup(*_args) -> None:
                self._active_workers.discard(worker)

            worker.signals.finished.connect(_cleanup)
            worker.signals.error.connect(_cleanup)
            self._threadpool.start(worker)
    ##############################
    #  Device Summary Page       #
    ##############################

    def refresh_devices(self) -> None:
        """@brief Query connected devices asynchronously.

        No-op while a long-running operation is in progress: re-enumerating
        devices mid-backup/restore/flash could reset current_device_udid
        (e.g. if the device momentarily drops off usbmuxd) while a worker is
        still bound to the old identifier, leaving the UI inconsistent with
        the operation actually running.
        """
        if self._busy:
            return
        worker = AsyncWorker(idevice.get_connected_devices)
        worker.signals.finished.connect(self.__on_devices_found)
        worker.signals.error.connect(lambda exc: print(self.tr("Error:"), exc))
        self._run_worker(worker)
        
    def check_usbdmux(self) -> None:
        """@brief Check whether usbmuxd is running asynchronously."""
        worker = AsyncWorker(idevice.check_usbmuxd)
        worker.signals.finished.connect(self.__on_usbdmux_checked)
        worker.signals.error.connect(lambda exc: print(self.tr("Error:"), exc))
        self._run_worker(worker)
        
    def __on_usbdmux_checked(self, result) -> None:
        """@brief Update the usbmuxd status and start it when necessary.

        @param result bool from check_usbmuxd, or UsbmuxdStatus from ensure_usbmuxd_running.
        """
        if isinstance(result, idevice.UsbmuxdStatus):
            if result == idevice.UsbmuxdStatus.FAILED:
                self.ui.usbmuxd_status_label.setText(self.tr("usbmuxd is NOT running"))
                self.__on_usbdmux_check_failed(self.tr(
                    "usbmuxd is not running and cannot be started from here. "
                    "Start it on your system with: sudo systemctl start usbmuxd"
                ))
            else:
                self.ui.usbmuxd_status_label.setText(self.tr("usbmuxd is running"))
            return

        if not result:
            worker = AsyncWorker(idevice.ensure_usbmuxd_running, gui=True)
            worker.signals.finished.connect(self.__on_usbdmux_checked)
            worker.signals.error.connect(lambda exc: self.__on_usbdmux_check_failed(exc))
            self._run_worker(worker)
            return

        self.ui.usbmuxd_status_label.setText("usbmuxd is running")
    
    def __on_usbdmux_check_failed(self, error):
        """@brief Show an error raised while checking or starting usbmuxd.

        @param error The exception raised by the usbmuxd operation.
        """
        QMessageBox.critical(
            self,
            self.tr("usbmuxd Not Running"),
            self.tr("Cound not start usbmuxd automatically. Please start it manually and try again.\n\nError: {error}").format(error=error)
        )

    def _load_device_summary(self, udid: str) -> None:
        """@brief Load a device summary asynchronously.

        @param udid The unique device identifier.
        """
        worker = AsyncWorker(idevice.get_device_summary, udid=udid)
        worker.signals.finished.connect(self.__on_summary_loaded)
        worker.signals.error.connect(lambda exc: print(self.tr("Errore summary:"), exc))
        self._run_worker(worker)

    def __on_summary_loaded(self, summary: dict) -> None:
        """@brief Display the loaded device summary.

        @param summary Device metadata returned by the device service.
        """
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
        """@brief Update the UI after discovering connected devices.

        Ignored while a long-running operation is in progress, for the same
        reason refresh_devices() itself is a no-op then: this callback could
        otherwise still land (e.g. from a refresh that started just before
        _set_busy(True)) and reset current_device_udid out from under an
        operation that is still running against the old identifier.

        @param devices The connected device records.
        """
        if self._busy:
            return

        if not devices:
            self.current_device_udid = None
            self.ui.deviceInfoLabel.setText(self.tr("No connected devices found."))
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
                self.tr("Multiple Devices Detected"),
                self.tr("Noot only supports one connected device at a time to prevent data loss or connection errors.\n"
                "Please disconnect all other devices and keep only the one you want to manage.")
            )
            self.current_device_udid = None
            self.ui.deviceInfoLabel.setText(self.tr("No connected devices found."))
            self.ui.deviceDetailsLabel.setText("")
              
    #############################
    # Backup Page: Encryption   #
    #############################

    def _check_backup_encryption(
        self,
        on_finished: Callable[[bool], None],
    ) -> None:
        """@brief Read the backup encryption state asynchronously.

        @param on_finished Callback receiving the encryption state.
        """
        if self.current_device_udid is None:
            return

        worker = AsyncWorker(
            idevice.is_backup_encrypted,
            udid=self.current_device_udid,
        )
        worker.signals.finished.connect(on_finished)
        worker.signals.error.connect(self.__on_encryption_state_check_failed)
        self._run_worker(worker)
    
    def _refresh_encryption_button_state(self) -> None:
        """@brief Refresh the encryption button text from the device state."""
        self._check_backup_encryption(self.__on_encryption_state_checked)
    
    def __on_encryption_state_checked(self, is_encrypted: bool) -> None:
        """@brief Update the encryption button according to the device state.

        @param is_encrypted Whether backup encryption is enabled.
        """
        self.ui.enableEncrypyionButton.setText(
            self.tr("Disable Encryption") if is_encrypted else self.tr("Enable Encryption")
        )
    
    def __changeEncryptionPassword(self):
        """@brief Prompt for passwords and change backup encryption asynchronously."""
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
            self._set_busy(True)
            worker.signals.finished.connect(self.__on_changeEncryptionPassword_finished)
            worker.signals.error.connect(self.__on_changeEncryptionPassword_failed)
            self._run_worker(worker)
        
        
    def __on_changeEncryptionPassword_finished(self, result):
        """@brief Handle a successful backup encryption password change.

        @param result The worker result, unused by this handler.
        """
        QMessageBox.information(
            self,
            self.tr("Password Changed"),
            self.tr("The backup encryption password has been changed successfully."),
        )
        self._set_busy(False)
        self._refresh_encryption_button_state()
    
    def __on_changeEncryptionPassword_failed(self, error):
        """@brief Handle a failed backup encryption password change.

        @param error The exception raised by the worker.
        """
        QMessageBox.critical(
            self,
            self.tr("Password Change Failed"),
            self.tr("Could not change the backup encryption password: {error}").format(error=error),
        )
        self._set_busy(False)
        self._refresh_encryption_button_state()
    
    def __enable_or_disable_Encryption(self):
        """@brief Determine the current state before changing backup encryption."""
        self._check_backup_encryption(self.__on_encryption_state_for_action_checked)

    def __on_encryption_state_for_action_checked(self, is_encrypted: bool):
        """@brief Ask for the required password and start the encryption action.

        @param is_encrypted Whether encryption is currently enabled.
        """
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
        self._set_busy(True)
        self._run_worker(worker)

    def __on_encryption_state_check_failed(self, error):
        """@brief Report a failure while reading the encryption state.

        @param error The exception raised by the worker.
        """
        QMessageBox.critical(
            self,
            self.tr("Encryption Status Check Failed"),
            self.tr("Could not determine the backup encryption status: {error}").format(error=error),
        )
            
    def __on_enable_encryption_finished(self, result):
        """@brief Handle successful encryption enablement.

        @param result The worker result, unused by this handler.
        """
        QMessageBox.information(
            self,
            self.tr("Encryption Enabled"),
            self.tr("Backup encryption has been enabled successfully."),
        )
        self._set_busy(False)
        self._refresh_encryption_button_state()
        
    def __on_enable_encryption_failed(self, error):
        """@brief Handle a failed encryption enablement.

        @param error The exception raised by the worker.
        """
        QMessageBox.critical(
            self,
            self.tr("Enabling Encryption Failed"),
            self.tr("Could not enable backup encryption: {error}").format(error=error),
        )
        self._set_busy(False)
    
    def __on_disable_encryption_finished(self, result):
        """@brief Handle successful encryption disablement.

        @param result The worker result, unused by this handler.
        """
        QMessageBox.information(
            self,
            self.tr("Encryption Disabled"),
            self.tr("Backup encryption has been disabled successfully."),
        )
        self._set_busy(False)
        self._refresh_encryption_button_state()
            
    def __on_disable_encryption_failed(self, error):
        """@brief Handle a failed encryption disablement.

        @param error The exception raised by the worker.
        """
        QMessageBox.critical(
            self,
            self.tr("Disabling Encryption Failed"),
            self.tr("Could not disable backup encryption: {error}").format(error=error),
        )
        self._set_busy(False)
        
    #############################
    # Backup Page: Execution    #
    #############################
    
    def __perform_backup(self):
        """@brief Validate the connected device and start the backup flow."""
        if self.current_device_udid is None:
            QMessageBox.critical(
                self,
                self.tr("No Device Connected"),
                self.tr("No device is currently connected. Please connect a device and try again."),
            )
            return

        self._check_backup_encryption(self.__start_backup_after_encryption_check)

    def __start_backup_after_encryption_check(self, is_encrypted: bool) -> None:
        """@brief Collect the backup password and launch the backup worker.

        @param is_encrypted Whether the device backup is encrypted.
        """
        password = ""
        if is_encrypted:
            password_dialog = EnterPasswordDialog(self)
            if password_dialog.exec() != QDialog.DialogCode.Accepted:
                return
            password = password_dialog.password()
        else:
            QMessageBox.information(
                self,
                self.tr("Backup Not Encrypted"),
                self.tr("Backup encryption is not enabled for this device.\n"
                "You will be prompted to set a password for the backup."),
            )
            password_dialog = SetPasswordDialog(self)
            if password_dialog.exec() != QDialog.DialogCode.Accepted:
                return
            password = password_dialog.password()

        self.ui.progressBar.setVisible(True)
        self.ui.progressBar.setMaximum(100)
        self.ui.progressBar.setValue(0)
        self.ui.progressLabel.setVisible(True)
        self.ui.progressLabel.setText(self.tr("Starting backup..."))
        self._set_busy(True)
        
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
            backup_dir=get_backup_directory(),
            full=full_backup,
            exclude=exclude,
            password=password,
            progress_callback=self.__on_backup_progress,
        )
        worker.signals.finished.connect(self.__on_backup_finished)
        worker.signals.error.connect(self.__on_backup_failed)
        self._run_worker(worker)

    def __on_backup_progress(self, percent: float) -> None:
        """@brief Update the backup progress controls.

        @param percent Current backup progress as a percentage.
        """
        self.ui.progressBar.setValue(round(percent))
        self.ui.progressLabel.setText(self.tr("Backing up..."))

    def __on_backup_finished(self, result) -> None:
        """@brief Handle a completed backup operation.

        @param result The worker result, unused by this handler.
        """
        QMessageBox.information(
            self,
            self.tr("Backup Completed"),
            self.tr("The backup completed successfully."),
        )
        self.ui.progressBar.setVisible(False)
        self.ui.progressLabel.setText("")
        self.ui.statusbar.showMessage(self.tr("Backup completed successfully."), 5000)
        self._set_busy(False)
    def __on_backup_failed(self, error) -> None:
        """@brief Handle a failed backup operation.

        @param error The exception raised by the worker.
        """
        QMessageBox.critical(
            self,
            self.tr("Backup Failed"),
            self.tr("Could not complete the backup: {error}").format(error=error),
        )
        self.ui.progressBar.setVisible(False)
        self.ui.progressLabel.setText("")
        self.ui.statusbar.showMessage(self.tr("Backup failed."), 5000)
        self._set_busy(False)
        
        
    ##############################
    # Restore Page:              #
    ##############################
    
    def __list_backups(self, backup_dir: Path | None = None) -> None:
        """@brief Load the available local backups asynchronously.

        @param backup_dir Directory containing local backups.
        """
        worker = AsyncWorker(idevice.list_local_backups, backup_dir=backup_dir)
        worker.signals.finished.connect(self.__on_backups_listed)
        worker.signals.error.connect(lambda exc: print(self.tr("Error:"), exc))
        self._run_worker(worker)
    
    def __on_backups_listed(self, backups: list[dict[str, str | datetime | None]]) -> None:
        """@brief Populate the backup selector with the discovered backups.

        @param backups Backup metadata returned by the worker.
        """
        self._local_backups = backups
        self.ui.local_backup_comboBox.clear()

        if not backups:
            self.ui.local_backup_comboBox.addItem(self.tr("No local backups found"))
            self.ui.local_backup_comboBox.setEnabled(False)
            self.ui.backup_details_label.setText(self.tr("No valid local backups found."))
            return

        self.ui.local_backup_comboBox.setEnabled(True)
        for backup in backups:
            device_name = backup.get("device_name") or self.tr("Unnamed device")
            backup_date = backup.get("backup_date")
            date_text = (
                backup_date.strftime("%Y-%m-%d %H:%M:%S")
                if isinstance(backup_date, datetime)
                else str(backup_date or self.tr("Unknown date"))
            )
            self.ui.local_backup_comboBox.addItem(
                f"{device_name} - {date_text}",
                backup.get("udid"),
            )

        self.__on_backup_selected(self.ui.local_backup_comboBox.currentIndex())

    def __on_backup_selected(self, index: int) -> None:
        """@brief Display details for the selected local backup.

        @param index Index of the selected backup in the combo box.
        """
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
            else str(backup_date or self.tr("Unknown date"))
        )
        self.ui.backup_details_label.setText(
            f"<b>BACKUP DATE:</b> {date_text}<br>"
            f"<b>DEVICE:</b> {backup.get('device_name') or self.tr('Unnamed device')}<br>"
            f"<b>UDID:</b> {udid}"
        )
        
        if(backup.get("udid") != self.current_device_udid):
            self.ui.different_device_warning.setVisible(True)
        else:
            self.ui.different_device_warning.setVisible(False)
            
    def __on_delete_backup(self):
        """@brief Confirm and delete the selected local backup."""
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
            self.tr("Delete Backup"),
            self.tr("Are you sure you want to delete the backup for device '{device_name}' dated '{backup_date}'?").format(
                device_name=str(backup.get("device_name") or self.tr("Unnamed device")),
                backup_date=str(backup.get("backup_date") or self.tr("Unknown date")),
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.ui.deleteBackupButton.setEnabled(False)

        worker = AsyncWorker(
            idevice.delete_local_backup,
            backup_dir=get_backup_directory(),
            udid=udid,
        )
        worker.signals.finished.connect(self.__on_backup_deleted)
        worker.signals.error.connect(self.__on_backup_delete_failed)
        self._run_worker(worker)

    def __on_backup_deleted(self, result) -> None:
        """@brief Handle successful backup deletion and refresh the list.

        @param result The worker result, unused by this handler.
        """
        self.ui.deleteBackupButton.setEnabled(True)
        self.ui.statusbar.showMessage(self.tr("Backup deleted successfully."), 5000)
        self.__list_backups()

    def __on_backup_delete_failed(self, error) -> None:
        """@brief Handle a failed local backup deletion.

        @param error The exception raised by the worker.
        """
        self.ui.deleteBackupButton.setEnabled(True)
        QMessageBox.critical(
            self,
            self.tr("Delete Backup Failed"),
            self.tr("Could not delete the backup: {error}").format(error=error),
        )
        self.ui.statusbar.showMessage(self.tr("Backup deletion failed."), 5000)
        
    def __perform_restore(self):
        """@brief Validate the selected backup and start the restore flow."""
        if self.current_device_udid is None:
            QMessageBox.critical(
                self,
                self.tr("No Device Connected"),
                self.tr("No device is currently connected. Please connect a device and try again."),
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

        device_name = backup.get("device_name") or self.tr("Unnamed device")
        confirm = QMessageBox.question(
            self,
            self.tr("Restore Backup"),
            self.tr("This will overwrite all data on the connected device with the backup "
            "for '{device_name}' dated '{backup_date}'. "
            "This operation cannot be undone. Continue?").format(
                device_name=device_name,
                backup_date=backup.get("backup_date") or self.tr("Unknown date"),
            ),
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
        self.ui.progressLabel.setText(self.tr("Starting restore..."))
        self._set_busy(True)

        worker = AsyncWorker(
            idevice.run_restore,
            udid=self.current_device_udid,
            backup_dir=get_backup_directory(),
            source_udid=source_udid,
            password=password,
            restore_system_files=True,
            progress_callback=self.__on_restore_progress,
        )
        worker.signals.finished.connect(self.__on_restore_finished)
        worker.signals.error.connect(self.__on_restore_failed)
        self._run_worker(worker)
        
    def __on_restore_progress(self, percent: float) -> None:
        """@brief Update the restore progress controls.

        @param percent Current restore progress as a percentage.
        """
        self.ui.progressBar.setValue(round(percent))
        self.ui.progressLabel.setText("Restoring...")
        
    def __on_restore_finished(self, result) -> None:
        """@brief Handle a completed restore operation.

        @param result The worker result, unused by this handler.
        """
        QMessageBox.information(
            self,
            self.tr("Restore Completed"),
            self.tr("The restore completed successfully."
            "Device will now reboot."),
        )
        self.ui.progressBar.setVisible(False)
        self.ui.progressLabel.setText("")
        self.ui.statusbar.showMessage(self.tr("Restore completed successfully."), 5000)
        self._set_busy(False)
        
    def __on_restore_failed(self, error) -> None:
        """@brief Handle a failed restore operation.

        @param error The exception raised by the worker.
        """
        QMessageBox.critical(
            self,
            self.tr("Restore Failed"),
            self.tr("Could not complete the restore: {error}").format(error=error),
        )
        self.ui.progressBar.setVisible(False)
        self.ui.progressLabel.setText("")
        self.ui.statusbar.showMessage(self.tr("Restore failed."), 5000)
        self._set_busy(False)
        
    #############################
    # iOS Version Tab           #
    #############################
    
    def __on_browse_ipsw(self):
        """@brief Select an IPSW file and load its metadata asynchronously."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select IPSW File",
            str(Path.home()),
            self.tr("IPSW Files (*.ipsw);;All Files (*)"),
        )
        if not file_path:
            return

        self.ui.ipswFilePathInput.setText(file_path)
        self.ui.ipswFileDetailsLabel.setText(self.tr("Reading IPSW file information..."))

        self.ui.browseIpswFileButton.setEnabled(False)
        worker = AsyncWorker(idevice.get_ipsw_file_info, file_path)
        worker.signals.finished.connect(
            lambda info: self.__on_ipsw_info_loaded(info, file_path)
        )
        worker.signals.error.connect(self.__on_ipsw_info_failed)
        self._run_worker(worker)

    def __on_ipsw_info_loaded(self, info: dict, file_path: str) -> None:
        """@brief Display IPSW metadata and check device compatibility.

        @param info Metadata extracted from the IPSW file.
        @param file_path Path to the selected IPSW file.
        """
        self.ui.browseIpswFileButton.setEnabled(True)
        self.ui.ipswFileDetailsLabel.setText(
            self.tr("* **Product Version:** {product_version}\n"
            "* **Product Build Version:** {product_build_version}\n"
            "* **Supported product types:** {supported_product_types}\n"
            "* **Build Major:** {build_mayor}").format(
                product_version=info.get('product_version', '<Not Available>'),
                product_build_version=info.get('product_build_version', '<Not Available>'),
                supported_product_types=', '.join(info.get('supported_product_types', [])),
                build_mayor=info.get('build_major', '<Not Available>')
            )
        )
        
        if self.current_device_udid is not None:
            self.__check_ipsw_compatibility(info, file_path)

    def __on_ipsw_info_failed(self, error: Exception) -> None:
        """@brief Report a failure while reading IPSW metadata.

        @param error The exception raised by the worker.
        """
        self.ui.browseIpswFileButton.setEnabled(True)
        self.ui.ipswFileDetailsLabel.setText(self.tr("Could not read the selected IPSW file."))
        QMessageBox.critical(
            self,
            self.tr("Invalid IPSW File"),
            self.tr("Could not read the selected IPSW file: {error}").format(error=error),
        )

    def __check_ipsw_compatibility(self, info: dict, file_path: str) -> None:
        """@brief Load the device summary for IPSW compatibility checking.

        @param info Metadata extracted from the selected IPSW file.
        @param file_path Path to the selected IPSW file.
        """
        worker = AsyncWorker(idevice.get_device_summary, udid=self.current_device_udid)
        worker.signals.finished.connect(
            lambda summary: self.__on_device_summary_for_compatibility(summary, info)
        )
        worker.signals.error.connect(self.__on_device_summary_failed)
        self._run_worker(worker)

    def __on_device_summary_for_compatibility(self, summary: dict, info: dict) -> None:
        """@brief Warn when the selected IPSW does not support the device.

        @param summary Device metadata used for compatibility checking.
        @param info IPSW metadata containing supported product types.
        """
        device_product_type = summary.get("modello")
        supported_types = info.get("supported_product_types", [])

        if device_product_type not in supported_types:
            QMessageBox.warning(
                self,
                self.tr("Incompatible IPSW"),
                ("The selected IPSW is not compatible with the connected device "
                "({device_product_type}).\n\n"
                "Supported product types for this IPSW: {supported_product_types}").format(
                    device_product_type=device_product_type,
                    supported_product_types=', '.join(supported_types)
                ),
            )
        
    def __on_device_summary_failed(self, exc: Exception) -> None:
        """@brief Report a failure while checking IPSW compatibility.

        @param exc The exception raised while loading the device summary.
        """
        QMessageBox.critical(
            self,
            self.tr("Error"),
            self.tr("Failed to fetch device summary. Please ensure the device is connected and try again.\n\n{exc}").format(exc=exc),
        )
        
    def __on_flash_ipsw(self):
        """@brief Validate the selected IPSW and start the flash operation.

        Resolves the flash target in one of two ways: a normally-booted
        device (current_device_udid) uses --udid; otherwise, before giving
        up, a DFU/Recovery/WTF probe is attempted so a device stuck there
        (e.g. after a failed prior update) can still be flashed via --ecid,
        matching what the CLI already supports through 'noot list-dfu'.
        """
        ipsw_file = self.ui.ipswFilePathInput.text().strip()
        if not ipsw_file:
            QMessageBox.warning(
                self,
                self.tr("No IPSW Selected"),
                self.tr("Please select an IPSW file before attempting to flash."),
            )
            return

        if self.current_device_udid is not None:
            self._start_flash(udid=self.current_device_udid, ecid=None, ipsw_file=ipsw_file)
            return

        # Nessun device normalmente bootato: prova a rilevare un device in DFU/Recovery/WTF
        # prima di arrenderti, cosi' un device gia' bloccato li' (es. dopo un update fallito)
        # resta comunque flashabile dalla GUI.
        self._probe_dfu_state(lambda device: self.__on_dfu_probed_for_flash(device, ipsw_file))

    def _probe_dfu_state(self, on_finished: Callable[[Optional[dict]], None]) -> None:
        """@brief Check whether a device is in DFU/Recovery/WTF mode asynchronously.

        Used as a fallback when no normally-booted device is selected, since
        such a device is invisible to usbmuxd and therefore has no UDID to
        offer.

        @param on_finished Callback receiving the boot-state device dict, or
            None if no such device was found (or the probe itself failed).
        """
        worker = AsyncWorker(idevice.get_boot_state_device)
        worker.signals.finished.connect(on_finished)
        worker.signals.error.connect(lambda exc: on_finished(None))
        self._run_worker(worker)

    def __on_dfu_probed_for_flash(self, device: Optional[dict], ipsw_file: str) -> None:
        """@brief Continue the flash flow once the DFU/Recovery/WTF probe returns.

        @param device The boot-state device dict, or None if none was found.
        @param ipsw_file Path to the selected IPSW file.
        """
        if device is None:
            QMessageBox.critical(
                self,
                self.tr("No Device Connected"),
                self.tr("No device is currently connected, and none was found in DFU/Recovery/WTF mode. "
                "Please connect a device and try again."),
            )
            return

        self._start_flash(udid=None, ecid=device["ecid"], ipsw_file=ipsw_file)

    def _start_flash(self, udid: Optional[str], ecid: Optional[int], ipsw_file: str) -> None:
        """@brief Confirm and launch the firmware flash worker.

        @param udid UDID of a normally-booted target device, mutually
            exclusive with ecid.
        @param ecid ECID of a device already in DFU/Recovery/WTF, mutually
            exclusive with udid.
        @param ipsw_file Path to the selected IPSW file.
        """
        erase = self.ui.eraseDataCheckBox.isChecked()
        
        #Question dialog to confirm flashing the device with the selected IPSW
        result = QMessageBox.question(
            self,
            self.tr("Confirm Flash"),
            self.tr("You are about to flash the device with the IPSW:\n{ipsw_file}\n\n"
            "Mode: {mode}\n\n"
            "The device will reboot into Recovery mode and stay unusable until the process completes.\n\n"
            "Do you want to continue?").format(
                ipsw_file=ipsw_file,
                mode='Erase and restore (factory reset)' if erase else 'Update (preserve data)'
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if(result != QMessageBox.StandardButton.Yes):
            return
        
        #If eraseDataCheckBox is checked, ask for confirmation
        if erase:
            result = QMessageBox.warning(
                self,
                self.tr("Warning"),
                self.tr("You have selected to erase all data on the device during the flash process. "
                "This will result in the loss of all data on the device. Are you sure you want to proceed?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            
            if(result != QMessageBox.StandardButton.Yes):
                return
            
        #Start Flashing Process
        self.ui.progressBar.setVisible(True)
        self.ui.progressBar.setMaximum(100)
        self.ui.progressBar.setValue(0)
        self.ui.progressLabel.setVisible(True)
        self._set_busy(True)
        
        worker = AsyncWorker(
            idevice.flash_from_ipsw,
            ipsw_path=ipsw_file,
            udid=udid,
            ecid=ecid,
            erase=erase,
            progress_callback=self.__on_flash_progress
        )
        worker.signals.finished.connect(self.__on_flash_completed)
        worker.signals.error.connect(self.__on_flash_failed)
        self._run_worker(worker)
        
    def __on_flash_progress(self, progress) -> None:
        """@brief Update the flash progress controls.

        @param progress Flash progress information from the worker.
        """
        self.ui.progressBar.setValue(round(progress.overall_progress))
        self.ui.progressLabel.setText(progress.step_label)
        
    def __on_flash_completed(self, _) -> None:
        """@brief Handle a completed firmware flash operation."""
        QMessageBox.information(
            self,
            self.tr("Flash Completed"),
            self.tr("The device has been flashed successfully. It will now reboot."),
        )
        self.ui.progressBar.setVisible(False)
        self.ui.progressBar.setMaximum(100)
        self.ui.progressBar.setValue(0)
        self.ui.progressLabel.setVisible(False)
        self.ui.statusbar.showMessage(self.tr("Flash completed successfully."), 5000)
        self._set_busy(False)
        
    def __on_flash_failed(self, error: Exception) -> None:
        """@brief Display the appropriate error for a failed flash operation.

        @param error The exception raised by the flash worker.
        """
        if isinstance(error, IdevicerestoreNotInstalledError):
            QMessageBox.critical(
                self,
                self.tr("idevicerestore Not Installed"),
                self.tr("idevicerestore is not installed on your system.\nInstall it with: sudo apt install idevicerestore"),
            )
        elif isinstance(error, IdevicerestoreError):
            QMessageBox.critical(
                self,
                self.tr("Flash Failed"),
                self.tr("The flash process failed: {error}").format(error=error),
            )
        elif isinstance(error, IdevicerestoreCancelledError):
            QMessageBox.information(
                self,
                self.tr("Flash Cancelled"),
                self.tr("The flash process was cancelled."),
            )
        else:
            QMessageBox.critical(
                self,
                self.tr("Flash Failed"),
                self.tr("Could not complete the flash process: {error}").format(error=error),
            )

        self.ui.progressBar.setVisible(False)
        self.ui.progressBar.setMaximum(100)
        self.ui.progressBar.setValue(0)
        self.ui.progressLabel.setVisible(False)
        self.ui.statusbar.showMessage("Flash failed.", 5000)
        self._set_busy(False)
        
    ###############################
    # Danger Zone                 #
    ###############################
                
    def __on_reboot_recovery(self):
        """@brief Confirm and reboot the connected device into recovery mode."""
        if self.current_device_udid is None:
            QMessageBox.critical(
                self,
                self.tr("No Device Connected"),
                self.tr("No device is currently connected. Please connect a device and try again."),
            )
            return
        
        result = QMessageBox.question(
            self,
            self.tr("Confirm Reboot to Recovery"),
            self.tr("You are about to reboot the connected device into Recovery mode.\n\n"
            "Do you want to continue?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if(result != QMessageBox.StandardButton.Yes):
            return
        
        worker = AsyncWorker(
            idevice.reboot_to_recovery,
            udid=self.current_device_udid
        )
        worker.signals.finished.connect(self.__on_reboot_recovery_completed)
        worker.signals.error.connect(self.__on_reboot_recovery_failed)
        self._run_worker(worker)
        
    def __on_reboot_recovery_completed(self, _) -> None:
        """@brief Report a successful reboot into recovery mode."""
        self.ui.statusbar.showMessage(self.tr("Device rebooted into Recovery mode."), 5000)
        
    def __on_reboot_recovery_failed(self, error: Exception) -> None:
        """@brief Report a failed reboot into recovery mode.

        @param error The exception raised by the worker.
        """
        QMessageBox.critical(
            self,
            self.tr("Reboot to Recovery Failed"),
            self.tr("Could not reboot the device into Recovery mode: {error}").format(error=error),
        )
        self.ui.statusbar.showMessage(self.tr("Reboot to Recovery failed."), 5000)  
    
    def __on_reboot_dfu(self):
        """@brief Provide instructions for entering DFU mode."""
        if self.current_device_udid is None:
            QMessageBox.critical(
                self,
                self.tr("No Device Connected"),
                self.tr("No device is currently connected. Please connect a device and try again."),
            )
            return
        
        # Instructions for entering DFU mode
        # TODO: Implement instructions for entering DFU mode based on device model
        
    def __on_factory_reset(self):
        """@brief Confirm the device identity and start a factory reset."""
        if self.current_device_udid is None:
            QMessageBox.critical(
                self,
                self.tr("No Device Connected"),
                self.tr("No device is currently connected. Please connect a device and try again."),
            )
            return
        
        confirm_udid = self.current_device_udid
        if get_ask_udid_confirmation():
            confirm_udid = QInputDialog.getText(
                self,
                self.tr("Confirm Device UDID"),
                self.tr("Please enter the device UDID to confirm the factory reset:"),
            )[0]
            
            if confirm_udid != self.current_device_udid:
                QMessageBox.critical(
                    self,
                    self.tr("UDID Mismatch"),
                    self.tr("The entered UDID does not match the connected device's UDID. "
                    "Factory reset has been cancelled."),
                )
                return
        
        result = QMessageBox.warning(
            self,
            self.tr("Confirm Factory Reset"),
            self.tr("You are about to perform a factory reset on the connected device. "
            "This will erase all data and settings on the device and restore it to its original state.\n\n"
            "Do you want to continue?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if(result != QMessageBox.StandardButton.Yes):
            return
        
        self.ui.progressBar.setVisible(True)
        self.ui.progressBar.setMaximum(100)
        self.ui.progressBar.setValue(0)
        self.ui.progressLabel.setVisible(True)
        self.ui.progressLabel.setText(self.tr("Starting factory reset..."))
        self._set_busy(True)
        
        worker = AsyncWorker(
            idevice.erase_device,
            udid=self.current_device_udid,
            confirm_udid=confirm_udid,
            progress_callback=self.__on_factory_reset_progress
        )
        worker.signals.finished.connect(self.__on_factory_reset_completed)
        worker.signals.error.connect(self.__on_factory_reset_failed)        
        self._run_worker(worker)
        
    def __on_factory_reset_progress(self, progress) -> None:
        """@brief Update the factory reset progress controls.

        @param progress Factory reset progress information from the worker.
        """
        self.ui.progressBar.setValue(round(progress.overall_progress))
        self.ui.progressLabel.setText(progress.step_label)
        
    def __on_factory_reset_completed(self, _) -> None:
        """@brief Handle a completed factory reset operation."""
        QMessageBox.information(
            self,
            self.tr("Factory Reset Completed"),
            self.tr("The device has been reset to factory settings successfully. It will now reboot."),
        )
        self.ui.progressBar.setVisible(False)
        self.ui.progressBar.setMaximum(100)
        self.ui.progressBar.setValue(0)
        self.ui.progressLabel.setVisible(False)
        self.ui.statusbar.showMessage(self.tr("Factory reset completed successfully."), 5000)
        self._set_busy(False)
    
    def __on_factory_reset_failed(self, error: Exception) -> None:
        """@brief Handle a failed factory reset operation.

        @param error The exception raised by the worker.
        """
        QMessageBox.critical(
            self,
            self.tr("Factory Reset Failed"),
            self.tr("Could not complete the factory reset: {error}"),
        )
        self.ui.progressBar.setVisible(False)
        self.ui.progressBar.setMaximum(100)
        self.ui.progressBar.setValue(0)
        self.ui.progressLabel.setVisible(False)
        self.ui.statusbar.showMessage(self.tr("Factory reset failed."), 5000)
        self._set_busy(False)
        
    #####################################
    # Shutdown and Reboot Actions      #
    #####################################
    
    def __on_shutdown(self):
        """@brief Confirm and shut down the connected device."""
        if self.current_device_udid is None:
            QMessageBox.critical(
                self,
                self.tr("No Device Connected"),
                self.tr("No device is currently connected. Please connect a device and try again."),
            )
            return
        
        result = QMessageBox.question(
            self,
            self.tr("Confirm Shutdown"),
            self.tr("Do you want to shutdown the device?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if(result != QMessageBox.StandardButton.Yes):
            return
        
        worker = AsyncWorker(
            idevice.shutdown_device,
            udid=self.current_device_udid
        )
        worker.signals.finished.connect(lambda _: self.ui.statusbar.showMessage(self.tr("Device shutdown successfully."), 5000))
        worker.signals.error.connect(lambda exc: QMessageBox.critical(self, self.tr("Shutdown Failed"), self.tr("Could not shutdown the device: {exc}").format(exc=exc)))
        self._run_worker(worker)
        
    def __on_reboot(self):
        """@brief Confirm and restart the connected device."""
        if self.current_device_udid is None:
            QMessageBox.critical(
                self,
                self.tr("No Device Connected"),
                self.tr("No device is currently connected. Please connect a device and try again."),
            )
            return
        
        result = QMessageBox.question(
            self,
            self.tr("Confirm Reboot"),
            self.tr("Do you want to reboot the device?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        
        if(result != QMessageBox.StandardButton.Yes):
            return
        
        worker = AsyncWorker(
            idevice.restart_device,
            udid=self.current_device_udid
        )
        worker.signals.finished.connect(lambda _: self.ui.statusbar.showMessage(self.tr("Device restarted successfully."), 5000))
        worker.signals.error.connect(lambda exc: QMessageBox.critical(self, self.tr("Reboot Failed"), self.tr("Could not reboot the device: {exc}").format(exc=exc)))
        self._run_worker(worker)