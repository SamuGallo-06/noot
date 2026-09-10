from PySide6.QtWidgets import QDialog, QMessageBox

from ui.ui_dialog_set_password import Ui_DialogSetPassword

class SetPasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_DialogSetPassword()
        self.ui.setupUi(self)
        
        self.ui.buttonBox.accepted.connect(self.__on_accept)
        
    def __on_accept(self):
        password = self.ui.newPasswordInput.text()
        confirm_password = self.ui.passwordConfirmInput.text()
        
        if password != confirm_password:
            QMessageBox.warning(self, "Password Mismatch", "The passwords do not match. Please try again.")
            return
        
        self.accept()

    def password(self) -> str:
        return self.ui.newPasswordInput.text()