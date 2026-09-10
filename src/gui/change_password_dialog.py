from PySide6.QtWidgets import QDialog, QMessageBox

from ui.ui_dialog_change_password import Ui_DialogChangePassword

class ChangePasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_DialogChangePassword()
        self.ui.setupUi(self)
        
        self.ui.buttonBox.accepted.connect(self.__on_accept)
        
    def __on_accept(self):
        password = self.ui.newPasswordInput.text()
        confirm_password = self.ui.passwordConfirmInput.text()
        
        if password != confirm_password:
            QMessageBox.warning(self, "Password Mismatch", "The passwords do not match. Please try again.")
            return
        
        self.accept()

    def password(self) -> tuple[str, str]:
        return self.ui.oldPasswordInput.text(), self.ui.newPasswordInput.text()