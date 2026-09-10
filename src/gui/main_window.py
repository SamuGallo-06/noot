from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QInputDialog,
    QLineEdit,
    QMainWindow,
    QMessageBox,
)

import idevice
from ui.ui_mainwindow import Ui_MainWindow

## Cartella di default per i backup locali. In futuro andra' sostituita da un
## valore letto/scritto tramite platformdirs + Preferences (vedi TODO in fondo).
DEFAULT_BACKUP_DIR = Path.home() / ".local" / "share" / "noot" / "backups"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        idevice.get_connected_devices()