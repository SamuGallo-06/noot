# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'dialog_change_passwordDSxdqI.ui'
##
## Created by: Qt User Interface Compiler version 6.11.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QAbstractButton, QApplication, QDialog, QDialogButtonBox,
    QGridLayout, QLabel, QLineEdit, QSizePolicy,
    QSpacerItem, QWidget)

class Ui_DialogChangePassword(object):
    def setupUi(self, DialogChangePassword):
        if not DialogChangePassword.objectName():
            DialogChangePassword.setObjectName(u"DialogChangePassword")
        DialogChangePassword.resize(400, 300)
        self.gridLayout = QGridLayout(DialogChangePassword)
        self.gridLayout.setObjectName(u"gridLayout")
        self.label_4 = QLabel(DialogChangePassword)
        self.label_4.setObjectName(u"label_4")

        self.gridLayout.addWidget(self.label_4, 3, 0, 1, 1)

        self.label_2 = QLabel(DialogChangePassword)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout.addWidget(self.label_2, 1, 0, 1, 1)

        self.label_3 = QLabel(DialogChangePassword)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout.addWidget(self.label_3, 2, 0, 1, 1)

        self.oldPasswordInput = QLineEdit(DialogChangePassword)
        self.oldPasswordInput.setObjectName(u"oldPasswordInput")
        self.oldPasswordInput.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)

        self.gridLayout.addWidget(self.oldPasswordInput, 1, 1, 1, 1)

        self.title = QLabel(DialogChangePassword)
        self.title.setObjectName(u"title")
        self.title.setTextFormat(Qt.TextFormat.RichText)

        self.gridLayout.addWidget(self.title, 0, 0, 1, 2)

        self.newPasswordInput = QLineEdit(DialogChangePassword)
        self.newPasswordInput.setObjectName(u"newPasswordInput")
        self.newPasswordInput.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)

        self.gridLayout.addWidget(self.newPasswordInput, 2, 1, 1, 1)

        self.buttonBox = QDialogButtonBox(DialogChangePassword)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.gridLayout.addWidget(self.buttonBox, 5, 1, 1, 1)

        self.passwordConfirmInput = QLineEdit(DialogChangePassword)
        self.passwordConfirmInput.setObjectName(u"passwordConfirmInput")
        self.passwordConfirmInput.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)

        self.gridLayout.addWidget(self.passwordConfirmInput, 3, 1, 1, 1)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.gridLayout.addItem(self.verticalSpacer, 4, 1, 1, 1)


        self.retranslateUi(DialogChangePassword)
        self.buttonBox.accepted.connect(DialogChangePassword.accept)
        self.buttonBox.rejected.connect(DialogChangePassword.reject)

        QMetaObject.connectSlotsByName(DialogChangePassword)
    # setupUi

    def retranslateUi(self, DialogChangePassword):
        DialogChangePassword.setWindowTitle(QCoreApplication.translate("DialogChangePassword", u"Dialog", None))
        self.label_4.setText(QCoreApplication.translate("DialogChangePassword", u"Confirm", None))
        self.label_2.setText(QCoreApplication.translate("DialogChangePassword", u"Previous Password: ", None))
        self.label_3.setText(QCoreApplication.translate("DialogChangePassword", u"New Password", None))
        self.oldPasswordInput.setInputMask("")
        self.title.setText(QCoreApplication.translate("DialogChangePassword", u"<html><head/><body><p><span style=\" font-size:12pt; font-weight:700;\">Change Encryption Password</span></p></body></html>", None))
        self.newPasswordInput.setInputMask("")
        self.passwordConfirmInput.setInputMask("")
    # retranslateUi

