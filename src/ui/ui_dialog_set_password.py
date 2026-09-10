# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'dialog_set_passwordjNSYpc.ui'
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

class Ui_DialogSetPassword(object):
    def setupUi(self, DialogSetPassword):
        if not DialogSetPassword.objectName():
            DialogSetPassword.setObjectName(u"DialogSetPassword")
        DialogSetPassword.resize(400, 261)
        self.gridLayout = QGridLayout(DialogSetPassword)
        self.gridLayout.setObjectName(u"gridLayout")
        self.newPasswordInput = QLineEdit(DialogSetPassword)
        self.newPasswordInput.setObjectName(u"newPasswordInput")
        self.newPasswordInput.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)

        self.gridLayout.addWidget(self.newPasswordInput, 1, 1, 1, 1)

        self.buttonBox = QDialogButtonBox(DialogSetPassword)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.gridLayout.addWidget(self.buttonBox, 4, 1, 1, 1)

        self.label_3 = QLabel(DialogSetPassword)
        self.label_3.setObjectName(u"label_3")

        self.gridLayout.addWidget(self.label_3, 1, 0, 1, 1)

        self.title = QLabel(DialogSetPassword)
        self.title.setObjectName(u"title")
        self.title.setTextFormat(Qt.TextFormat.RichText)

        self.gridLayout.addWidget(self.title, 0, 0, 1, 2)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.gridLayout.addItem(self.verticalSpacer, 3, 1, 1, 1)

        self.passwordConfirmInput = QLineEdit(DialogSetPassword)
        self.passwordConfirmInput.setObjectName(u"passwordConfirmInput")
        self.passwordConfirmInput.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)

        self.gridLayout.addWidget(self.passwordConfirmInput, 2, 1, 1, 1)

        self.label_4 = QLabel(DialogSetPassword)
        self.label_4.setObjectName(u"label_4")

        self.gridLayout.addWidget(self.label_4, 2, 0, 1, 1)


        self.retranslateUi(DialogSetPassword)
        self.buttonBox.accepted.connect(DialogSetPassword.accept)
        self.buttonBox.rejected.connect(DialogSetPassword.reject)

        QMetaObject.connectSlotsByName(DialogSetPassword)
    # setupUi

    def retranslateUi(self, DialogSetPassword):
        DialogSetPassword.setWindowTitle(QCoreApplication.translate("DialogSetPassword", u"Dialog", None))
        self.label_3.setText(QCoreApplication.translate("DialogSetPassword", u"New Password", None))
        self.title.setText(QCoreApplication.translate("DialogSetPassword", u"<html><head/><body><p><span style=\" font-size:12pt; font-weight:700;\">Set Encryption Password</span></p></body></html>", None))
        self.label_4.setText(QCoreApplication.translate("DialogSetPassword", u"Confirm", None))
    # retranslateUi

