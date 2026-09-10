# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'dialog_enter_passwordzOqgkd.ui'
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

class Ui_DialogEnterPassword(object):
    def setupUi(self, DialogEnterPassword):
        if not DialogEnterPassword.objectName():
            DialogEnterPassword.setObjectName(u"DialogEnterPassword")
        DialogEnterPassword.resize(400, 261)
        self.gridLayout = QGridLayout(DialogEnterPassword)
        self.gridLayout.setObjectName(u"gridLayout")
        self.lineEdit_2 = QLineEdit(DialogEnterPassword)
        self.lineEdit_2.setObjectName(u"lineEdit_2")
        self.lineEdit_2.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)

        self.gridLayout.addWidget(self.lineEdit_2, 1, 1, 1, 1)

        self.buttonBox = QDialogButtonBox(DialogEnterPassword)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)

        self.gridLayout.addWidget(self.buttonBox, 3, 1, 1, 1)

        self.title = QLabel(DialogEnterPassword)
        self.title.setObjectName(u"title")
        self.title.setTextFormat(Qt.TextFormat.RichText)

        self.gridLayout.addWidget(self.title, 0, 0, 1, 2)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.gridLayout.addItem(self.verticalSpacer, 2, 1, 1, 1)


        self.retranslateUi(DialogEnterPassword)
        self.buttonBox.accepted.connect(DialogEnterPassword.accept)
        self.buttonBox.rejected.connect(DialogEnterPassword.reject)

        QMetaObject.connectSlotsByName(DialogEnterPassword)
    # setupUi

    def retranslateUi(self, DialogEnterPassword):
        DialogEnterPassword.setWindowTitle(QCoreApplication.translate("DialogEnterPassword", u"Dialog", None))
        self.title.setText(QCoreApplication.translate("DialogEnterPassword", u"<html><head/><body><p><span style=\" font-size:12pt; font-weight:700;\">Enter Encryption Password</span></p></body></html>", None))
    # retranslateUi

