"""Controller della finestra principale di Noot.

Questo file NON contiene widget definiti a mano: la struttura visiva vive
interamente in ``ui_mainwindow.py``, generato da Qt Designer e rigenerato
automaticamente ogni volta che il file .ui viene ricompilato (vedi il
warning in cima a quel file: "All changes made in this file will be lost
when recompiling"). MainWindow eredita da QMainWindow e compone Ui_MainWindow
tramite ``self.ui = Ui_MainWindow()``, cosi' i due file restano completamente
disaccoppiati:

  - ui_mainwindow.py  -> SOLO struttura visiva, si rigenera da Designer
  - main_window.py    -> SOLO logica: collega segnali, chiama idevice.py,
                         aggiorna i widget esposti da self.ui

Ogni chiamata a idevice.py che puo' durare piu' di qualche istante (backup,
restore, erase, enable/disable encryption) passa da AsyncWorker per non
bloccare il thread della GUI.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

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
from gui.async_worker import AsyncWorker
from gui.confirm_dialog import ConfirmUdidDialog
from ui.ui_mainwindow import Ui_MainWindow

## Cartella di default per i backup locali. In futuro andra' sostituita da un
## valore letto/scritto tramite platformdirs + Preferences (vedi TODO in fondo).
DEFAULT_BACKUP_DIR = Path.home() / ".local" / "share" / "noot" / "backups"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        ## Pool di thread per le operazioni async lanciate da AsyncWorker.
        ## Un solo worker alla volta ha senso qui: due backup/restore/erase
        ## in parallelo sullo stesso device non sono un caso da supportare.
        self._threadpool = QThreadPool()
        self._threadpool.setMaxThreadCount(1)

        ## Stato applicativo minimo tenuto a mano finche' non serve altro.
        self._current_udid: Optional[str] = None
        self._connected_devices: list[dict] = []
        self._backup_dir: Path = DEFAULT_BACKUP_DIR

        self._connect_signals()
        self._set_actions_enabled(False)  # nessun device finche' non ne troviamo uno
        self.refresh_devices()

    ## ------------------------------------------------------------------
    ## Setup e wiring dei segnali
    ## ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        ui = self.ui

        ## Menu File
        ui.actionExit.triggered.connect(self.close)
        ui.actionPreferences.triggered.connect(self._open_preferences)

        ## Menu Help
        ui.actionHow_to_Enter_DFU_mode.triggered.connect(self._show_dfu_instructions)

        ## Tab Backup
        ui.pushButton.clicked.connect(self._on_perform_backup)  # "Perform Backup"
        ui.pushButton_2.clicked.connect(self._on_toggle_encryption)  # "Enable/Disable"
        ui.pushButton_3.clicked.connect(self._on_change_password)  # "Change Password"
        ## checkBox_7 = "Full Backup": se disattivata (incremental) le
        ## esclusioni non sono ammesse, vedi IncrementalExcludeConflictError.
        ui.checkBox_7.toggled.connect(self._on_full_backup_toggled)

        ## Tab Restore
        ui.local_backup_comboBox.currentIndexChanged.connect(self._on_backup_selection_changed)
        ui.start_restore_button.clicked.connect(self._on_perform_restore)
        ui.deleteBackupButton.clicked.connect(self._on_delete_backup)
        ui.openBackupFolderButton.clicked.connect(self._on_open_backup_folder)

        ## Tab Danger Zone
        ui.eraseDeviceButton.clicked.connect(self._on_erase_device)
        ui.recoveryModeButton.clicked.connect(self._on_toggle_recovery_mode)
        ## Il pulsante Erase resta disabilitato finche' la checkbox non e' spuntata.
        ui.checkBox_8.toggled.connect(ui.eraseDeviceButton.setEnabled)
        ui.eraseDeviceButton.setEnabled(False)

    def _set_actions_enabled(self, enabled: bool) -> None:
        """Abilita/disabilita in blocco le azioni che richiedono un device connesso."""
        ui = self.ui
        for widget in (
            ui.pushButton, ui.pushButton_2, ui.pushButton_3,
            ui.start_restore_button, ui.deleteBackupButton,
            ui.recoveryModeButton, ui.tabWidget,
        ):
            widget.setEnabled(enabled)
        ## eraseDeviceButton resta gestito a parte dalla checkbox di conferma.
        if not enabled:
            ui.eraseDeviceButton.setEnabled(False)
            ui.checkBox_8.setChecked(False)

    ## ------------------------------------------------------------------
    ## Device discovery / stato usbmuxd
    ## ------------------------------------------------------------------

    def refresh_devices(self) -> None:
        worker = AsyncWorker(idevice.get_connected_devices)
        worker.signals.finished.connect(self._on_devices_found)
        worker.signals.error.connect(self._on_generic_error)
        self._threadpool.start(worker)

    def _on_devices_found(self, devices: list[dict]) -> None:
        self._connected_devices = devices or []
        if not self._connected_devices:
            self._current_udid = None
            self._set_actions_enabled(False)
            self.ui.deviceDetailsLabel.setText("### No device connected\nConnect an iPhone or iPad via USB")
            self.ui.usbmuxd_status_label.setText("usbmuxd: unknown")
            return

        ## Nessuna combobox in UI per la selezione: se piu' device sono
        ## connessi si prende il primo, la selezione esplicita passera' dal
        ## menu Device -> Select Device (da implementare quando quel menu
        ## avra' le relative QAction in ui_mainwindow.py).
        first = self._connected_devices[0]
        self._current_udid = first["udid"]
        self._set_actions_enabled(True)
        self._load_device_summary(self._current_udid) #type: ignore
        self._refresh_local_backups()

    def _load_device_summary(self, udid: str) -> None:
        worker = AsyncWorker(idevice.get_device_summary, udid=udid)
        worker.signals.finished.connect(self._on_summary_loaded)
        worker.signals.error.connect(self._on_generic_error)
        self._threadpool.start(worker)

    def _on_summary_loaded(self, summary: dict) -> None:
        ui = self.ui
        model = summary.get("modello") or "Unknown model"
        name = summary.get("nome") or "Unnamed device"
        ui.deviceDetailsLabel.setText(f"### {model}\n{name}")
        ui.usbmuxd_status_label.setText("usbmuxd: OK")

        storage_total = summary.get("storage_totale_gb")
        storage_free = summary.get("storage_libero_gb")
        storage_line = (
            f"{storage_total - storage_free:.1f} / {storage_total} GB"
            if storage_total and storage_free is not None
            else "N/A"
        )

        ui.deviceInfoLabel.setText(
            f"<b>Device Name</b>: {name}<br/>"
            f"<b>Hardware:</b> {summary.get('hardware', 'N/A')}<br/>"
            f"<b>iOS Version</b>: {summary.get('ios_version', 'N/A')}<br/>"
            f"<b>Build</b>: {summary.get('build', 'N/A')}<br/>"
            f"<b>Serial</b>: {summary.get('serial', 'N/A')}<br/>"
            f"<b>UDID</b>: {summary.get('udid', 'N/A')}<br/>"
            f"<b>Storage</b>: {storage_line}<br/>"
            f"<b>WiFi MAC</b>: {summary.get('wifi_mac', 'N/A')}<br/>"
            f"<b>Bluetooth MAC</b>: {summary.get('bluetooth_mac', 'N/A')}"
        )

    ## ------------------------------------------------------------------
    ## Tab Backup
    ## ------------------------------------------------------------------

    def _on_full_backup_toggled(self, checked: bool) -> None:
        """Le categorie di esclusione richiedono full=True (vedi idevice.run_backup).

        Se l'utente disattiva "Full Backup" (quindi vuole un incremental),
        le checkbox di esclusione vengono disabilitate anziche' lasciare che
        l'utente scopra IncrementalExcludeConflictError dopo aver premuto
        "Perform Backup".
        """
        ui = self.ui
        exclude_checkboxes = self._exclude_checkboxes()
        for checkbox in exclude_checkboxes:
            checkbox.setEnabled(checked)
            if not checked:
                checkbox.setChecked(False)

    def _exclude_checkboxes(self):
        """Ritorna la mappa {QCheckBox: nome_categoria} per le esclusioni backup.

        I nomi devono coincidere con le chiavi reali di
        idevice.EXCLUDABLE_CATEGORIES (BackupSelection), non con label
        inventate in UI: eventuali differenze di maiuscole/minuscole vanno
        risolte qui, in un unico punto, non sparse nella UI.
        """
        ui = self.ui
        return {
            ui.checkBox: "Bookmarks",
            ui.checkBox_2: "Call history",
            ui.checkBox_3: "Contacts",
            ui.checkBox_4: "Messages",
            ui.checkBox_5: "Sms",
            ui.checkBox_6: "Whatsapp",
        }

    def _on_perform_backup(self) -> None:
        if not self._current_udid:
            return

        full = self.ui.checkBox_7.isChecked()
        exclude = [name for checkbox, name in self._exclude_checkboxes().items() if checkbox.isChecked()]

        password, ok = QInputDialog.getText(
            self, "Backup Password", "Enter backup encryption password:",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return

        self._backup_dir.mkdir(parents=True, exist_ok=True)
        self.ui.pushButton.setEnabled(False)
        self.ui.progressLabel.setText("Running: Backup")

        worker = AsyncWorker(
            idevice.run_backup,
            udid=self._current_udid,
            backup_dir=self._backup_dir,
            full=full,
            exclude=exclude,
            password=password,
        )
        worker.signals.progress.connect(self._on_progress)
        worker.signals.finished.connect(self._on_backup_finished)
        worker.signals.error.connect(self._on_backup_error)
        self._threadpool.start(worker)

    def _on_backup_finished(self, _result) -> None:
        self.ui.pushButton.setEnabled(True)
        self.ui.progressBar.setValue(100)
        self.ui.progressLabel.setText("Backup completed")
        self._refresh_local_backups()

    def _on_backup_error(self, exc: Exception) -> None:
        self.ui.pushButton.setEnabled(True)
        self.ui.progressLabel.setText("Backup failed")
        if isinstance(exc, idevice.EncryptionNotEnabledError):
            QMessageBox.warning(self, "Encryption required", str(exc))
        elif isinstance(exc, idevice.IncrementalExcludeConflictError):
            QMessageBox.warning(self, "Invalid options", str(exc))
        else:
            self._on_generic_error(exc)

    def _on_toggle_encryption(self) -> None:
        if not self._current_udid:
            return
        password, ok = QInputDialog.getText(
            self, "Backup Encryption", "Enter a password to enable encryption:",
            QLineEdit.EchoMode.Password,
        )
        if not ok or not password:
            return
        worker = AsyncWorker(idevice.enable_backup_encryption, udid=self._current_udid, password=password)
        worker.signals.finished.connect(lambda _: QMessageBox.information(self, "Encryption", "Encryption enabled."))
        worker.signals.error.connect(self._on_generic_error)
        self._threadpool.start(worker)

    def _on_change_password(self) -> None:
        if not self._current_udid:
            return
        old_password, ok = QInputDialog.getText(
            self, "Change Password", "Current password:", QLineEdit.EchoMode.Password,
        )
        if not ok:
            return
        new_password, ok = QInputDialog.getText(
            self, "Change Password", "New password:", QLineEdit.EchoMode.Password,
        )
        if not ok:
            return
        worker = AsyncWorker(
            idevice.change_backup_encryption_password,
            udid=self._current_udid, old_password=old_password, new_password=new_password,
        )
        worker.signals.finished.connect(lambda _: QMessageBox.information(self, "Password", "Password changed."))
        worker.signals.error.connect(self._on_generic_error)
        self._threadpool.start(worker)

    ## ------------------------------------------------------------------
    ## Tab Restore
    ## ------------------------------------------------------------------

    def _refresh_local_backups(self) -> None:
        backups = idevice.list_local_backups(self._backup_dir)
        combo = self.ui.local_backup_comboBox
        combo.blockSignals(True)
        combo.clear()
        for backup in backups:
            label = f"{backup.get('backup_date')} · {backup.get('device_name') or 'Unknown'}"
            combo.addItem(label, userData=backup)
        combo.blockSignals(False)
        self._on_backup_selection_changed(combo.currentIndex())

    def _on_backup_selection_changed(self, index: int) -> None:
        combo = self.ui.local_backup_comboBox
        backup = combo.itemData(index) if index >= 0 else None
        if not backup:
            self.ui.backup_details_label.setText("")
            self.ui.different_device_warning.setVisible(False)
            return

        self.ui.backup_details_label.setText(
            f"<b>BACKUP DATE:</b> {backup.get('backup_date')}<br/>"
            f"<b>DEVICE:</b> {backup.get('device_name')}<br/>"
            f"<b>UDID:</b> {backup.get('udid')}"
        )
        is_different = bool(self._current_udid and backup.get("udid") != self._current_udid)
        self.ui.different_device_warning.setVisible(is_different)

    def _on_perform_restore(self) -> None:
        if not self._current_udid:
            return
        combo = self.ui.local_backup_comboBox
        backup = combo.itemData(combo.currentIndex())
        if not backup:
            QMessageBox.warning(self, "No backup selected", "Select a backup to restore first.")
            return

        dialog = ConfirmUdidDialog(expected_udid=self._current_udid, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        password, _ok = QInputDialog.getText(
            self, "Restore Password", "Backup password (leave empty if not encrypted):",
            QLineEdit.EchoMode.Password,
        )

        self.ui.start_restore_button.setEnabled(False)
        self.ui.progressLabel.setText("Running: Restore")

        worker = AsyncWorker(
            idevice.run_restore,
            udid=self._current_udid,
            backup_dir=self._backup_dir,
            source_udid=backup.get("udid"),
            password=password,
        )
        worker.signals.progress.connect(self._on_progress)
        worker.signals.finished.connect(self._on_restore_finished)
        worker.signals.error.connect(self._on_restore_error)
        self._threadpool.start(worker)

    def _on_restore_finished(self, _result) -> None:
        self.ui.start_restore_button.setEnabled(True)
        self.ui.progressBar.setValue(100)
        self.ui.progressLabel.setText("Restore completed")

    def _on_restore_error(self, exc: Exception) -> None:
        self.ui.start_restore_button.setEnabled(True)
        self.ui.progressLabel.setText("Restore failed")
        if isinstance(exc, idevice.RestorePasswordRequiredError):
            QMessageBox.warning(self, "Password required", str(exc))
        elif isinstance(exc, idevice.IncorrectBackupPasswordError):
            QMessageBox.warning(self, "Incorrect password", str(exc))
        elif isinstance(exc, idevice.BackupNotFoundError):
            QMessageBox.warning(self, "Backup not found", str(exc))
        else:
            self._on_generic_error(exc)

    def _on_delete_backup(self) -> None:
        combo = self.ui.local_backup_comboBox
        backup = combo.itemData(combo.currentIndex())
        if not backup:
            return
        reply = QMessageBox.question(
            self, "Delete backup",
            f"Delete the local backup from {backup.get('backup_date')}? This cannot be undone.",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        import shutil
        shutil.rmtree(self._backup_dir / backup["udid"], ignore_errors=True)
        self._refresh_local_backups()

    def _on_open_backup_folder(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._backup_dir)))

    ## ------------------------------------------------------------------
    ## Tab Danger Zone
    ## ------------------------------------------------------------------

    def _on_erase_device(self) -> None:
        if not self._current_udid:
            return
        dialog = ConfirmUdidDialog(expected_udid=self._current_udid, parent=self, destructive_label="Erase Device")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.ui.eraseDeviceButton.setEnabled(False)
        self.ui.progressLabel.setText("Running: Erase")

        worker = AsyncWorker(idevice.erase_device, udid=self._current_udid, confirm_udid=self._current_udid)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.finished.connect(lambda _: self.ui.progressLabel.setText("Erase completed"))
        worker.signals.error.connect(self._on_generic_error)
        self._threadpool.start(worker)

    def _on_toggle_recovery_mode(self) -> None:
        ## TODO: idevice.py non espone ancora enter/exit recovery mode.
        ## Quando la funzione sara' disponibile, sostituire questo placeholder
        ## con un AsyncWorker come per le altre azioni.
        QMessageBox.information(
            self, "Not implemented yet",
            "Recovery Mode control is not implemented in idevice.py yet.",
        )

    ## ------------------------------------------------------------------
    ## Help / Preferences
    ## ------------------------------------------------------------------

    def _open_preferences(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Backup location", str(self._backup_dir),
        )
        if directory:
            self._backup_dir = Path(directory)
            self._refresh_local_backups()

    def _show_dfu_instructions(self) -> None:
        QMessageBox.information(
            self, "How to Enter DFU Mode",
            "DFU Mode cannot be triggered remotely: it requires a manual "
            "button sequence on the device itself. Refer to the Noot wiki "
            "for the exact sequence for your device model.",
        )

    ## ------------------------------------------------------------------
    ## Helper condivisi
    ## ------------------------------------------------------------------

    def _on_progress(self, value: float) -> None:
        self.ui.progressBar.setValue(int(value))

    def _on_generic_error(self, exc: Exception) -> None:
        QMessageBox.critical(self, "Error", str(exc))