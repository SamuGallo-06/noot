from PySide6.QtWidgets import QDialog

from ui.ui_dialog_enter_password import Ui_DialogEnterPassword

class EnterPasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_DialogEnterPassword()
        self.ui.setupUi(self)

    def password(self) -> str:
        return self.ui.lineEdit_2.text()