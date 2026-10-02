from PySide6.QtWidgets import QDialog, QDialogButtonBox, QMessageBox

from ui.ui_settings import Ui_PreferencesDialog
import settings

class PreferencesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_PreferencesDialog()
        self.ui.setupUi(self)
        self.load_settings()
        self.ui.buttonBox.clicked.connect(self.__on_buttonbox_clicked)
        
    def __on_buttonbox_clicked(self, button):
        
        pressed = self.ui.buttonBox.standardButton(button)
        
        if pressed == QDialogButtonBox.StandardButton.Apply:
            print(self.tr("Saving settings..."))
            self.save_settings()
            self.close()
        elif pressed == pressed == QDialogButtonBox.StandardButton.Close:
            print(self.tr("Closing..."))
            confirm = QMessageBox.question(self, self.tr("Confirm Close"), self.tr("Are you sure you want to close the settings dialog?"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if confirm == QMessageBox.StandardButton.Yes:
                self.close()
            else:
                return
        elif pressed == QDialogButtonBox.StandardButton.RestoreDefaults:
            print(self.tr("Restored default values"))
            self.restore_defaults()
        elif pressed == QDialogButtonBox.StandardButton.Reset:
            print(self.tr("Resetting to last saved values..."))
            self.load_settings()
            
    def load_settings(self):
        cfg = settings.load()
        self.ui.backupLibraryPathInput.setText(cfg.get("paths", "backup"))
        self.ui.idevicerestorePathInput.setText(cfg.get("paths", "idevicerestore"))
        self.ui.askUdidCheckBox.setChecked(cfg.get("misc", "ask_udid_confirmation") == "True")
        #Ui
        self.ui.languageComboBox.setCurrentText(cfg.get("ui", "language"))
        self.ui.themeComboBox.setCurrentText(cfg.get("ui", "theme"))
        
    def save_settings(self):
        cfg = settings.load()
        cfg.set("paths", "backup_directory", self.ui.backupLibraryPathInput.text())
        cfg.set("paths", "idevicerestore", self.ui.idevicerestorePathInput.text())
        cfg.set("misc", "ask_udid_confirmation", str(self.ui.askUdidCheckBox.isChecked()))
        cfg.set("ui", "language", self.ui.languageComboBox.currentText())
        cfg.set("ui", "theme", self.ui.themeComboBox.currentText())
        settings.save(cfg)
        
    def restore_defaults(self):
        cfg = settings.load()
        cfg.read_dict(settings.DEFAULTS)
        self.ui.backupLibraryPathInput.setText(cfg.get("paths", "backup_directory"))
        self.ui.idevicerestorePathInput.setText(cfg.get("paths", "idevicerestore"))
        self.ui.askUdidCheckBox.setChecked(cfg.get("misc", "ask_udid_confirmation") == "True")
        #Ui
        self.ui.languageComboBox.setCurrentText(cfg.get("ui", "language"))
        self.ui.themeComboBox.setCurrentText(cfg.get("ui", "theme"))