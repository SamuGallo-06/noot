# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'settingsbLmvsy.ui'
##
## Created by: Qt User Interface Compiler version 6.11.2
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
from PySide6.QtWidgets import (QAbstractButton, QApplication, QCheckBox, QComboBox,
    QDialogButtonBox, QGridLayout, QLabel, QLineEdit,
    QPushButton, QSizePolicy, QSpacerItem, QWidget)

class Ui_PreferencesDialog(object):
    def setupUi(self, PreferencesDialog):
        if not PreferencesDialog.objectName():
            PreferencesDialog.setObjectName(u"PreferencesDialog")
        PreferencesDialog.resize(564, 487)
        self.gridLayout = QGridLayout(PreferencesDialog)
        self.gridLayout.setObjectName(u"gridLayout")
        self.horizontalSpacer = QSpacerItem(10, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer, 6, 0, 1, 1)

        self.label = QLabel(PreferencesDialog)
        self.label.setObjectName(u"label")
        self.label.setTextFormat(Qt.TextFormat.MarkdownText)

        self.gridLayout.addWidget(self.label, 5, 0, 1, 5)

        self.label_7 = QLabel(PreferencesDialog)
        self.label_7.setObjectName(u"label_7")

        self.gridLayout.addWidget(self.label_7, 4, 1, 1, 1)

        self.languageComboBox = QComboBox(PreferencesDialog)
        self.languageComboBox.addItem("")
        self.languageComboBox.addItem("")
        self.languageComboBox.setObjectName(u"languageComboBox")

        self.gridLayout.addWidget(self.languageComboBox, 4, 2, 1, 3)

        self.label_2 = QLabel(PreferencesDialog)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout.addWidget(self.label_2, 6, 1, 1, 1)

        self.horizontalSpacer_2 = QSpacerItem(10, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_2, 9, 0, 1, 1)

        self.askUdidCheckBox = QCheckBox(PreferencesDialog)
        self.askUdidCheckBox.setObjectName(u"askUdidCheckBox")

        self.gridLayout.addWidget(self.askUdidCheckBox, 9, 1, 1, 4)

        self.label_5 = QLabel(PreferencesDialog)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setTextFormat(Qt.TextFormat.MarkdownText)

        self.gridLayout.addWidget(self.label_5, 2, 0, 1, 5)

        self.horizontalSpacer_3 = QSpacerItem(10, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

        self.gridLayout.addItem(self.horizontalSpacer_3, 7, 0, 1, 1)

        self.idevicerestorePathInput = QLineEdit(PreferencesDialog)
        self.idevicerestorePathInput.setObjectName(u"idevicerestorePathInput")

        self.gridLayout.addWidget(self.idevicerestorePathInput, 7, 2, 1, 2)

        self.themeComboBox = QComboBox(PreferencesDialog)
        self.themeComboBox.addItem("")
        self.themeComboBox.addItem("")
        self.themeComboBox.addItem("")
        self.themeComboBox.setObjectName(u"themeComboBox")

        self.gridLayout.addWidget(self.themeComboBox, 3, 2, 1, 3)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.gridLayout.addItem(self.verticalSpacer, 10, 2, 1, 1)

        self.label_4 = QLabel(PreferencesDialog)
        self.label_4.setObjectName(u"label_4")
        self.label_4.setTextFormat(Qt.TextFormat.MarkdownText)

        self.gridLayout.addWidget(self.label_4, 7, 1, 1, 1)

        self.browseBackupPathButton = QPushButton(PreferencesDialog)
        self.browseBackupPathButton.setObjectName(u"browseBackupPathButton")

        self.gridLayout.addWidget(self.browseBackupPathButton, 6, 4, 1, 1)

        self.label_3 = QLabel(PreferencesDialog)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setTextFormat(Qt.TextFormat.MarkdownText)

        self.gridLayout.addWidget(self.label_3, 8, 0, 1, 5)

        self.backupLibraryPathInput = QLineEdit(PreferencesDialog)
        self.backupLibraryPathInput.setObjectName(u"backupLibraryPathInput")

        self.gridLayout.addWidget(self.backupLibraryPathInput, 6, 2, 1, 2)

        self.browseIdevicerestoreButton = QPushButton(PreferencesDialog)
        self.browseIdevicerestoreButton.setObjectName(u"browseIdevicerestoreButton")

        self.gridLayout.addWidget(self.browseIdevicerestoreButton, 7, 4, 1, 1)

        self.label_6 = QLabel(PreferencesDialog)
        self.label_6.setObjectName(u"label_6")

        self.gridLayout.addWidget(self.label_6, 3, 1, 1, 1)

        self.buttonBox = QDialogButtonBox(PreferencesDialog)
        self.buttonBox.setObjectName(u"buttonBox")
        self.buttonBox.setStandardButtons(QDialogButtonBox.StandardButton.Apply|QDialogButtonBox.StandardButton.Close|QDialogButtonBox.StandardButton.Reset|QDialogButtonBox.StandardButton.RestoreDefaults)

        self.gridLayout.addWidget(self.buttonBox, 11, 0, 1, 5)


        self.retranslateUi(PreferencesDialog)

        QMetaObject.connectSlotsByName(PreferencesDialog)
    # setupUi

    def retranslateUi(self, PreferencesDialog):
        PreferencesDialog.setWindowTitle(QCoreApplication.translate("PreferencesDialog", u"Noot Settings", None))
        self.label.setText(QCoreApplication.translate("PreferencesDialog", u"### Paths", None))
        self.label_7.setText(QCoreApplication.translate("PreferencesDialog", u"Language", None))
        self.languageComboBox.setItemText(0, QCoreApplication.translate("PreferencesDialog", u"English", None))
        self.languageComboBox.setItemText(1, QCoreApplication.translate("PreferencesDialog", u"Italian", None))

        self.label_2.setText(QCoreApplication.translate("PreferencesDialog", u"Backup Library Path", None))
        self.askUdidCheckBox.setText(QCoreApplication.translate("PreferencesDialog", u"Ask for UDID confirmation for dangerous operations", None))
        self.label_5.setText(QCoreApplication.translate("PreferencesDialog", u"### Ui", None))
        self.themeComboBox.setItemText(0, QCoreApplication.translate("PreferencesDialog", u"Use System Settings", None))
        self.themeComboBox.setItemText(1, QCoreApplication.translate("PreferencesDialog", u"Light", None))
        self.themeComboBox.setItemText(2, QCoreApplication.translate("PreferencesDialog", u"Dark", None))

        self.label_4.setText(QCoreApplication.translate("PreferencesDialog", u"`idevicerestore` path", None))
        self.browseBackupPathButton.setText(QCoreApplication.translate("PreferencesDialog", u"Browse", None))
        self.label_3.setText(QCoreApplication.translate("PreferencesDialog", u"### Security", None))
        self.browseIdevicerestoreButton.setText(QCoreApplication.translate("PreferencesDialog", u"Browse", None))
        self.label_6.setText(QCoreApplication.translate("PreferencesDialog", u"Theme", None))
    # retranslateUi

