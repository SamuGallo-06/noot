"""Dialog di conferma per operazioni distruttive (erase, restore).

Riproduce nella GUI lo stesso pattern di sicurezza gia' usato in main.py per
la CLI: l'utente deve ridigitare l'UDID esatto del device per abilitare il
pulsante di conferma. Nessuna scorciatoia da tastiera (Invio/Spazio) puo'
attivare l'azione finche' il testo non combacia esattamente.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


class ConfirmUdidDialog(QDialog):
    def __init__(self, expected_udid: str, parent=None, destructive_label: str = "Confirm") -> None:
        super().__init__(parent)
        self._expected_udid = expected_udid

        self.setWindowTitle("Final confirmation")
        self.setModal(True)

        layout = QVBoxLayout(self)

        warning = QLabel(
            f"You are about to perform an irreversible action:\n"
            f"<b>{destructive_label}</b>\n\n"
            f"UDID: {expected_udid}\n\n"
            f"Type the device UDID above to confirm:"
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)

        self._input = QLineEdit()
        self._input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._input)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText(destructive_label)
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

    def _on_text_changed(self, text: str) -> None:
        matches = text.strip() == self._expected_udid
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(matches)
