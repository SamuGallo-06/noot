# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'mainwindowdDVreF.ui'
##
## Created by: Qt User Interface Compiler version 6.11.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QAction, QBrush, QColor, QConicalGradient,
    QCursor, QFont, QFontDatabase, QGradient,
    QIcon, QImage, QKeySequence, QLinearGradient,
    QPainter, QPalette, QPixmap, QRadialGradient,
    QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
    QGridLayout, QLabel, QLineEdit, QMainWindow,
    QMenu, QMenuBar, QProgressBar, QPushButton,
    QSizePolicy, QSpacerItem, QStatusBar, QTabWidget,
    QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(801, 599)
        self.actionAbout_Noot = QAction(MainWindow)
        self.actionAbout_Noot.setObjectName(u"actionAbout_Noot")
        self.actionWiki = QAction(MainWindow)
        self.actionWiki.setObjectName(u"actionWiki")
        self.actionGitHub_Repository = QAction(MainWindow)
        self.actionGitHub_Repository.setObjectName(u"actionGitHub_Repository")
        self.actionHow_to_Enter_DFU_mode = QAction(MainWindow)
        self.actionHow_to_Enter_DFU_mode.setObjectName(u"actionHow_to_Enter_DFU_mode")
        self.actionPreferences = QAction(MainWindow)
        self.actionPreferences.setObjectName(u"actionPreferences")
        self.actionExit = QAction(MainWindow)
        self.actionExit.setObjectName(u"actionExit")
        self.actionRefresh_Devices = QAction(MainWindow)
        self.actionRefresh_Devices.setObjectName(u"actionRefresh_Devices")
        self.actionReport_Issue = QAction(MainWindow)
        self.actionReport_Issue.setObjectName(u"actionReport_Issue")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.gridLayout = QGridLayout(self.centralwidget)
        self.gridLayout.setObjectName(u"gridLayout")
        self.progressBar = QProgressBar(self.centralwidget)
        self.progressBar.setObjectName(u"progressBar")
        self.progressBar.setValue(24)

        self.gridLayout.addWidget(self.progressBar, 4, 1, 1, 2)

        self.progressLabel = QLabel(self.centralwidget)
        self.progressLabel.setObjectName(u"progressLabel")

        self.gridLayout.addWidget(self.progressLabel, 4, 0, 1, 1)

        self.tabWidget = QTabWidget(self.centralwidget)
        self.tabWidget.setObjectName(u"tabWidget")
        self.summary_tab = QWidget()
        self.summary_tab.setObjectName(u"summary_tab")
        self.gridLayout_2 = QGridLayout(self.summary_tab)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.deviceInfoLabel = QLabel(self.summary_tab)
        self.deviceInfoLabel.setObjectName(u"deviceInfoLabel")
        self.deviceInfoLabel.setTextFormat(Qt.TextFormat.MarkdownText)
        self.deviceInfoLabel.setWordWrap(True)

        self.gridLayout_2.addWidget(self.deviceInfoLabel, 0, 0, 1, 1)

        self.tabWidget.addTab(self.summary_tab, "")
        self.backup_tab = QWidget()
        self.backup_tab.setObjectName(u"backup_tab")
        self.gridLayout_3 = QGridLayout(self.backup_tab)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.latest_backup_label = QLabel(self.backup_tab)
        self.latest_backup_label.setObjectName(u"latest_backup_label")

        self.gridLayout_3.addWidget(self.latest_backup_label, 0, 0, 1, 1)

        self.excludeBookmarksCheckBox = QCheckBox(self.backup_tab)
        self.excludeBookmarksCheckBox.setObjectName(u"excludeBookmarksCheckBox")

        self.gridLayout_3.addWidget(self.excludeBookmarksCheckBox, 7, 0, 1, 1)

        self.fullBackupCheckBox = QCheckBox(self.backup_tab)
        self.fullBackupCheckBox.setObjectName(u"fullBackupCheckBox")

        self.gridLayout_3.addWidget(self.fullBackupCheckBox, 4, 0, 1, 1)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_3.addItem(self.verticalSpacer_2, 2, 0, 1, 3)

        self.excludeSMSCheckBox = QCheckBox(self.backup_tab)
        self.excludeSMSCheckBox.setObjectName(u"excludeSMSCheckBox")

        self.gridLayout_3.addWidget(self.excludeSMSCheckBox, 8, 1, 1, 1)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_3.addItem(self.verticalSpacer, 9, 1, 1, 1)

        self.verticalSpacer_3 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_3.addItem(self.verticalSpacer_3, 12, 1, 1, 1)

        self.excludeWhatsappCheckBox = QCheckBox(self.backup_tab)
        self.excludeWhatsappCheckBox.setObjectName(u"excludeWhatsappCheckBox")

        self.gridLayout_3.addWidget(self.excludeWhatsappCheckBox, 8, 0, 1, 1)

        self.label_5 = QLabel(self.backup_tab)
        self.label_5.setObjectName(u"label_5")
        self.label_5.setTextFormat(Qt.TextFormat.MarkdownText)

        self.gridLayout_3.addWidget(self.label_5, 3, 0, 1, 3)

        self.label = QLabel(self.backup_tab)
        self.label.setObjectName(u"label")

        self.gridLayout_3.addWidget(self.label, 10, 0, 1, 2)

        self.label_6 = QLabel(self.backup_tab)
        self.label_6.setObjectName(u"label_6")

        self.gridLayout_3.addWidget(self.label_6, 6, 0, 1, 1)

        self.enableEncrypyionButton = QPushButton(self.backup_tab)
        self.enableEncrypyionButton.setObjectName(u"enableEncrypyionButton")

        self.gridLayout_3.addWidget(self.enableEncrypyionButton, 10, 2, 1, 1)

        self.performBackupButton = QPushButton(self.backup_tab)
        self.performBackupButton.setObjectName(u"performBackupButton")

        self.gridLayout_3.addWidget(self.performBackupButton, 15, 0, 1, 3)

        self.excludeMessagesCheckBox = QCheckBox(self.backup_tab)
        self.excludeMessagesCheckBox.setObjectName(u"excludeMessagesCheckBox")

        self.gridLayout_3.addWidget(self.excludeMessagesCheckBox, 8, 2, 1, 1)

        self.excludeContactsCheckBox = QCheckBox(self.backup_tab)
        self.excludeContactsCheckBox.setObjectName(u"excludeContactsCheckBox")

        self.gridLayout_3.addWidget(self.excludeContactsCheckBox, 7, 1, 1, 1)

        self.excludeCallHistoryCheckBox = QCheckBox(self.backup_tab)
        self.excludeCallHistoryCheckBox.setObjectName(u"excludeCallHistoryCheckBox")

        self.gridLayout_3.addWidget(self.excludeCallHistoryCheckBox, 7, 2, 1, 1)

        self.changeEncryptionpasswordButton = QPushButton(self.backup_tab)
        self.changeEncryptionpasswordButton.setObjectName(u"changeEncryptionpasswordButton")

        self.gridLayout_3.addWidget(self.changeEncryptionpasswordButton, 11, 2, 1, 1)

        self.tabWidget.addTab(self.backup_tab, "")
        self.restore_tab = QWidget()
        self.restore_tab.setObjectName(u"restore_tab")
        self.gridLayout_4 = QGridLayout(self.restore_tab)
        self.gridLayout_4.setObjectName(u"gridLayout_4")
        self.verticalSpacer_6 = QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.gridLayout_4.addItem(self.verticalSpacer_6, 4, 0, 1, 3)

        self.verticalSpacer_4 = QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.gridLayout_4.addItem(self.verticalSpacer_4, 6, 0, 1, 3)

        self.label_2 = QLabel(self.restore_tab)
        self.label_2.setObjectName(u"label_2")

        self.gridLayout_4.addWidget(self.label_2, 0, 0, 1, 1)

        self.local_backup_comboBox = QComboBox(self.restore_tab)
        self.local_backup_comboBox.setObjectName(u"local_backup_comboBox")

        self.gridLayout_4.addWidget(self.local_backup_comboBox, 0, 1, 1, 2)

        self.start_restore_button = QPushButton(self.restore_tab)
        self.start_restore_button.setObjectName(u"start_restore_button")

        self.gridLayout_4.addWidget(self.start_restore_button, 7, 0, 1, 3)

        self.different_device_warning = QLabel(self.restore_tab)
        self.different_device_warning.setObjectName(u"different_device_warning")

        self.gridLayout_4.addWidget(self.different_device_warning, 5, 0, 1, 2)

        self.verticalSpacer_5 = QSpacerItem(20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.gridLayout_4.addItem(self.verticalSpacer_5, 2, 0, 1, 3)

        self.backup_details_label = QLabel(self.restore_tab)
        self.backup_details_label.setObjectName(u"backup_details_label")
        self.backup_details_label.setTextFormat(Qt.TextFormat.RichText)
        self.backup_details_label.setWordWrap(True)

        self.gridLayout_4.addWidget(self.backup_details_label, 3, 0, 1, 3)

        self.deleteBackupButton = QPushButton(self.restore_tab)
        self.deleteBackupButton.setObjectName(u"deleteBackupButton")

        self.gridLayout_4.addWidget(self.deleteBackupButton, 1, 1, 1, 1)

        self.openBackupFolderButton = QPushButton(self.restore_tab)
        self.openBackupFolderButton.setObjectName(u"openBackupFolderButton")

        self.gridLayout_4.addWidget(self.openBackupFolderButton, 1, 2, 1, 1)

        self.tabWidget.addTab(self.restore_tab, "")
        self.version_tab = QWidget()
        self.version_tab.setObjectName(u"version_tab")
        self.gridLayout_6 = QGridLayout(self.version_tab)
        self.gridLayout_6.setObjectName(u"gridLayout_6")
        self.label_11 = QLabel(self.version_tab)
        self.label_11.setObjectName(u"label_11")

        self.gridLayout_6.addWidget(self.label_11, 8, 0, 1, 1)

        self.line_2 = QFrame(self.version_tab)
        self.line_2.setObjectName(u"line_2")
        self.line_2.setFrameShape(QFrame.Shape.HLine)
        self.line_2.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout_6.addWidget(self.line_2, 1, 0, 1, 3)

        self.checkSigningStatusButton = QPushButton(self.version_tab)
        self.checkSigningStatusButton.setObjectName(u"checkSigningStatusButton")

        self.gridLayout_6.addWidget(self.checkSigningStatusButton, 8, 2, 1, 1)

        self.verticalSpacer_12 = QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.gridLayout_6.addItem(self.verticalSpacer_12, 4, 0, 1, 1)

        self.flashFirmwareButton = QPushButton(self.version_tab)
        self.flashFirmwareButton.setObjectName(u"flashFirmwareButton")

        self.gridLayout_6.addWidget(self.flashFirmwareButton, 10, 0, 1, 3)

        self.label_10 = QLabel(self.version_tab)
        self.label_10.setObjectName(u"label_10")

        self.gridLayout_6.addWidget(self.label_10, 6, 0, 1, 1)

        self.browseIpswFileButton = QPushButton(self.version_tab)
        self.browseIpswFileButton.setObjectName(u"browseIpswFileButton")

        self.gridLayout_6.addWidget(self.browseIpswFileButton, 6, 2, 1, 1)

        self.verticalSpacer_10 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_6.addItem(self.verticalSpacer_10, 9, 1, 1, 1)

        self.ipswFilePathInput = QLineEdit(self.version_tab)
        self.ipswFilePathInput.setObjectName(u"ipswFilePathInput")

        self.gridLayout_6.addWidget(self.ipswFilePathInput, 6, 1, 1, 1)

        self.signingStatusLabel = QLabel(self.version_tab)
        self.signingStatusLabel.setObjectName(u"signingStatusLabel")

        self.gridLayout_6.addWidget(self.signingStatusLabel, 8, 1, 1, 1)

        self.label_9 = QLabel(self.version_tab)
        self.label_9.setObjectName(u"label_9")

        self.gridLayout_6.addWidget(self.label_9, 5, 0, 1, 3)

        self.verticalSpacer_13 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

        self.gridLayout_6.addItem(self.verticalSpacer_13, 7, 1, 1, 1)

        self.label_8 = QLabel(self.version_tab)
        self.label_8.setObjectName(u"label_8")
        self.label_8.setTextFormat(Qt.TextFormat.RichText)
        self.label_8.setWordWrap(True)

        self.gridLayout_6.addWidget(self.label_8, 0, 0, 1, 3)

        self.verticalSpacer_11 = QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.gridLayout_6.addItem(self.verticalSpacer_11, 2, 0, 1, 1)

        self.currentIosVersionLabel = QLabel(self.version_tab)
        self.currentIosVersionLabel.setObjectName(u"currentIosVersionLabel")

        self.gridLayout_6.addWidget(self.currentIosVersionLabel, 3, 0, 1, 3)

        self.tabWidget.addTab(self.version_tab, "")
        self.danger_tab = QWidget()
        self.danger_tab.setObjectName(u"danger_tab")
        self.gridLayout_5 = QGridLayout(self.danger_tab)
        self.gridLayout_5.setObjectName(u"gridLayout_5")
        self.recoveryModeButton = QPushButton(self.danger_tab)
        self.recoveryModeButton.setObjectName(u"recoveryModeButton")

        self.gridLayout_5.addWidget(self.recoveryModeButton, 5, 1, 1, 1)

        self.label_4 = QLabel(self.danger_tab)
        self.label_4.setObjectName(u"label_4")
        self.label_4.setTextFormat(Qt.TextFormat.RichText)
        self.label_4.setWordWrap(True)

        self.gridLayout_5.addWidget(self.label_4, 7, 0, 1, 2)

        self.verticalSpacer_8 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.gridLayout_5.addItem(self.verticalSpacer_8, 9, 0, 1, 2)

        self.label_7 = QLabel(self.danger_tab)
        self.label_7.setObjectName(u"label_7")
        self.label_7.setWordWrap(True)

        self.gridLayout_5.addWidget(self.label_7, 4, 0, 1, 2)

        self.verticalSpacer_7 = QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.gridLayout_5.addItem(self.verticalSpacer_7, 3, 0, 1, 1)

        self.eraseDeviceButton = QPushButton(self.danger_tab)
        self.eraseDeviceButton.setObjectName(u"eraseDeviceButton")

        self.gridLayout_5.addWidget(self.eraseDeviceButton, 8, 1, 1, 1)

        self.line = QFrame(self.danger_tab)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.Shape.HLine)
        self.line.setFrameShadow(QFrame.Shadow.Sunken)

        self.gridLayout_5.addWidget(self.line, 2, 0, 1, 2)

        self.checkBox_8 = QCheckBox(self.danger_tab)
        self.checkBox_8.setObjectName(u"checkBox_8")

        self.gridLayout_5.addWidget(self.checkBox_8, 8, 0, 1, 1)

        self.label_3 = QLabel(self.danger_tab)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setWordWrap(True)

        self.gridLayout_5.addWidget(self.label_3, 0, 0, 1, 2)

        self.verticalSpacer_9 = QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

        self.gridLayout_5.addItem(self.verticalSpacer_9, 6, 0, 1, 1)

        self.tabWidget.addTab(self.danger_tab, "")

        self.gridLayout.addWidget(self.tabWidget, 3, 0, 1, 3)

        self.bootStatusLabel = QLabel(self.centralwidget)
        self.bootStatusLabel.setObjectName(u"bootStatusLabel")
        self.bootStatusLabel.setTextFormat(Qt.TextFormat.RichText)

        self.gridLayout.addWidget(self.bootStatusLabel, 1, 2, 1, 1)

        self.usbmuxd_status_label = QLabel(self.centralwidget)
        self.usbmuxd_status_label.setObjectName(u"usbmuxd_status_label")

        self.gridLayout.addWidget(self.usbmuxd_status_label, 2, 2, 1, 1)

        self.deviceDetailsLabel = QLabel(self.centralwidget)
        self.deviceDetailsLabel.setObjectName(u"deviceDetailsLabel")
        self.deviceDetailsLabel.setTextFormat(Qt.TextFormat.MarkdownText)

        self.gridLayout.addWidget(self.deviceDetailsLabel, 1, 0, 2, 2)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 801, 23))
        self.menuFile = QMenu(self.menubar)
        self.menuFile.setObjectName(u"menuFile")
        self.menuDevice = QMenu(self.menubar)
        self.menuDevice.setObjectName(u"menuDevice")
        self.menuHelp = QMenu(self.menubar)
        self.menuHelp.setObjectName(u"menuHelp")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuDevice.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())
        self.menuFile.addAction(self.actionPreferences)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.actionExit)
        self.menuDevice.addAction(self.actionRefresh_Devices)
        self.menuHelp.addAction(self.actionAbout_Noot)
        self.menuHelp.addAction(self.actionWiki)
        self.menuHelp.addAction(self.actionGitHub_Repository)
        self.menuHelp.addSeparator()
        self.menuHelp.addAction(self.actionHow_to_Enter_DFU_mode)
        self.menuHelp.addAction(self.actionReport_Issue)

        self.retranslateUi(MainWindow)

        self.tabWidget.setCurrentIndex(1)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"MainWindow", None))
        self.actionAbout_Noot.setText(QCoreApplication.translate("MainWindow", u"About Noot", None))
        self.actionWiki.setText(QCoreApplication.translate("MainWindow", u"Wiki", None))
        self.actionGitHub_Repository.setText(QCoreApplication.translate("MainWindow", u"GitHub Repository", None))
        self.actionHow_to_Enter_DFU_mode.setText(QCoreApplication.translate("MainWindow", u"How to Enter DFU mode", None))
        self.actionPreferences.setText(QCoreApplication.translate("MainWindow", u"Preferences", None))
        self.actionExit.setText(QCoreApplication.translate("MainWindow", u"Exit", None))
#if QT_CONFIG(shortcut)
        self.actionExit.setShortcut(QCoreApplication.translate("MainWindow", u"Ctrl+Q", None))
#endif // QT_CONFIG(shortcut)
        self.actionRefresh_Devices.setText(QCoreApplication.translate("MainWindow", u"Refresh Devices", None))
        self.actionReport_Issue.setText(QCoreApplication.translate("MainWindow", u"Report Issue", None))
        self.progressLabel.setText(QCoreApplication.translate("MainWindow", u"Running:", None))
        self.deviceInfoLabel.setText(QCoreApplication.translate("MainWindow", u"No Connected Device", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.summary_tab), QCoreApplication.translate("MainWindow", u"Summary", None))
        self.latest_backup_label.setText(QCoreApplication.translate("MainWindow", u"Latest Backup: ", None))
        self.excludeBookmarksCheckBox.setText(QCoreApplication.translate("MainWindow", u"Bookmarks", None))
        self.fullBackupCheckBox.setText(QCoreApplication.translate("MainWindow", u"Full Backup", None))
        self.excludeSMSCheckBox.setText(QCoreApplication.translate("MainWindow", u"SMS", None))
        self.excludeWhatsappCheckBox.setText(QCoreApplication.translate("MainWindow", u"Whatsapp", None))
        self.label_5.setText(QCoreApplication.translate("MainWindow", u"**Backup Options**", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"Backup Encryption", None))
        self.label_6.setText(QCoreApplication.translate("MainWindow", u"Exclude from backup: ", None))
        self.enableEncrypyionButton.setText(QCoreApplication.translate("MainWindow", u"Enable/Disable", None))
        self.performBackupButton.setText(QCoreApplication.translate("MainWindow", u"Perform Backup", None))
        self.excludeMessagesCheckBox.setText(QCoreApplication.translate("MainWindow", u"Messages", None))
        self.excludeContactsCheckBox.setText(QCoreApplication.translate("MainWindow", u"Contacts", None))
        self.excludeCallHistoryCheckBox.setText(QCoreApplication.translate("MainWindow", u"Call History", None))
        self.changeEncryptionpasswordButton.setText(QCoreApplication.translate("MainWindow", u"Change Password", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.backup_tab), QCoreApplication.translate("MainWindow", u"Backup", None))
        self.label_2.setText(QCoreApplication.translate("MainWindow", u"Backup stored on this computer:", None))
        self.start_restore_button.setText(QCoreApplication.translate("MainWindow", u"Start Restore", None))
        self.different_device_warning.setText(QCoreApplication.translate("MainWindow", u"<html><head/><body><p><span style=\" font-weight:700; color:#ff7800;\">WARNING: </span></p><p><span style=\" color:#ff7800;\">This backup was made from a different device. Some data may not restore correctly.</span></p></body></html>", None))
        self.backup_details_label.setText(QCoreApplication.translate("MainWindow", u"<html><head/><body><p><span style=\" font-weight:700;\">BACKUP DATE:</span> 2026-09-08 14:32</p><p><span style=\" font-weight:700;\">DEVICE:</span> Samuele's iPhone</p><p><span style=\" font-weight:700;\">IOS VERSION:</span> 18.4</p><p><span style=\" font-weight:700;\">SIZE:</span> 1.2 GB</p><p><span style=\" font-weight:700;\">ENCRYPTED:</span> Yes</p></body></html>", None))
        self.deleteBackupButton.setText(QCoreApplication.translate("MainWindow", u"Delete", None))
        self.openBackupFolderButton.setText(QCoreApplication.translate("MainWindow", u"Open Backup Folder", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.restore_tab), QCoreApplication.translate("MainWindow", u"Restore", None))
        self.label_11.setText(QCoreApplication.translate("MainWindow", u"Signing Status: ", None))
        self.checkSigningStatusButton.setText(QCoreApplication.translate("MainWindow", u"Check Signing Status", None))
        self.flashFirmwareButton.setText(QCoreApplication.translate("MainWindow", u"Flash Firmware", None))
        self.label_10.setText(QCoreApplication.translate("MainWindow", u"IPSW File: ", None))
        self.browseIpswFileButton.setText(QCoreApplication.translate("MainWindow", u"Browse...", None))
        self.signingStatusLabel.setText(QCoreApplication.translate("MainWindow", u"\u23f3 Not checked yet ", None))
        self.label_9.setText(QCoreApplication.translate("MainWindow", u"Flash Firmware from IPSW", None))
        self.label_8.setText(QCoreApplication.translate("MainWindow", u"<html><head/><body><p><span style=\" color:#ff7800;\">Downgrading/upgrading via custom IPSW may void warranty, brick your device, or fail if Apple no longer signs that firmware. Proceed at your own risk. Noot and its author assume no responsibility for data loss or device damage.</span></p></body></html>", None))
        self.currentIosVersionLabel.setText(QCoreApplication.translate("MainWindow", u"Current iOS Version: ", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.version_tab), QCoreApplication.translate("MainWindow", u"iOS Version", None))
        self.recoveryModeButton.setText(QCoreApplication.translate("MainWindow", u"Enter/Exit Recovery Mode", None))
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"<html><head/><body><p><span style=\" font-size:12pt; font-weight:700;\">Erase Device</span></p><p>This will permanently erase all content and settings from this device, restoring it to factory defaults. This includes photos, messages, apps, and all personal data. This action cannot be undone.</p></body></html>", None))
        self.label_7.setText(QCoreApplication.translate("MainWindow", u"<html><head/><body><p><span style=\" font-size:12pt; font-weight:700;\">Recovery Mode</span></p><p>Restart the device into Recovery Mode. This is required for firmware restore operations and can also help resolve devices stuck after a failed update. The device will disconnect and restart automatically. .</p></body></html>", None))
        self.eraseDeviceButton.setText(QCoreApplication.translate("MainWindow", u"Erase Device", None))
        self.checkBox_8.setText(QCoreApplication.translate("MainWindow", u"I understand this will permanently erase all data on this device", None))
        self.label_3.setText(QCoreApplication.translate("MainWindow", u"<html><head/><body><p><span style=\" font-weight:700; color:#f66151;\">Actions in this section are irreversible and will permanently affect your device. Proceed only if you understand the consequences. </span></p></body></html>", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.danger_tab), QCoreApplication.translate("MainWindow", u"Danger Zone", None))
        self.bootStatusLabel.setText(QCoreApplication.translate("MainWindow", u"<html><head/><body><p><span style=\" font-weight:700; color:#1c71d8;\">Recovery Mode / DFU Mode</span></p></body></html>", None))
        self.usbmuxd_status_label.setText(QCoreApplication.translate("MainWindow", u" usbmuxd: OK", None))
        self.deviceDetailsLabel.setText(QCoreApplication.translate("MainWindow", u"### iPhone XR\n"
"Samuele's iPhone ", None))
        self.menuFile.setTitle(QCoreApplication.translate("MainWindow", u"File", None))
        self.menuDevice.setTitle(QCoreApplication.translate("MainWindow", u"Device", None))
        self.menuHelp.setTitle(QCoreApplication.translate("MainWindow", u"Help", None))
    # retranslateUi

