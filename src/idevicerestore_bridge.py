"""Ponte verso il binario esterno ``idevicerestore`` (progetto libimobiledevice).

Perche' questo modulo esiste separato da idevice.py: idevice.py parla con
pymobiledevice3 in-process (chiamate Python dirette, eccezioni tipizzate).
idevicerestore e' invece un binario C esterno, invocato come sottoprocesso:
il modello di comunicazione (stdout/stderr testuali, codici di uscita,
cancellazione di un processo invece che di una coroutine) e' sufficientemente
diverso da meritare un modulo a se', per non mescolare due stili radicalmente
diversi nello stesso file.

Perche' idevicerestore al posto di pymobiledevice3.restore.Restore: quella
libreria richiede il formato Image4 (guard esplicito in
BaseRestore.ensure_image4_supported), quindi non funziona su device pre-A7
(es. iPad mini 1, iPhone 5c), che usano ancora il formato Image3. Il codice
IMG3 esiste in pymobiledevice3 (TSSRequest.add_ap_img3_tags) ma e'
irraggiungibile a causa di quel guard incondizionato — sembra incompleto/mai
finito upstream, non una feature attiva. idevicerestore, al contrario, supporta
IMG3 end-to-end da 15+ anni ed e' oggi usato come motore unico per QUALSIASI
device (pre-A7 incluso), sostituendo interamente il percorso pymobiledevice3.

Il binario espone un flag pensato apposta per l'uso da programma esterno:
``-P/--plain-progress`` stampa righe stabili nel formato
``progress: {step} {step_progress}\\n`` su stdout, con fflush esplicito dopo
ogni riga (verificato nel sorgente C, idevicerestore.c:1751-1755). Gli errori
vanno su stderr con prefisso ``ERROR: `` (verificato empiricamente). Questo
rende il parsing dell'output affidabile: non serve interpretare la barra di
progresso colorata/interattiva pensata per un terminale umano.

Dipendenza di sistema, non pip-installabile:
    sudo apt install idevicerestore
Porta con se' libirecovery, libimobiledevice-glue, libplist, libtatsu come
dipendenze a cascata (gestite da apt). Verificato disponibile su Ubuntu
24.04/Zorin OS 18 con supporto a --plain-progress incluso (pacchetto
1.0.0-3build5, stesso flag anche nella build "stabile", non solo nelle
snapshot git piu' recenti).
"""
from __future__ import annotations

import asyncio
import re
import shutil
from dataclasses import dataclass
from enum import IntEnum
from typing import Callable, Optional


class IdevicerestoreNotInstalledError(Exception):
    """@brief Raised when the ``idevicerestore`` binary is not found on PATH.

    :seealso: Install with ``sudo apt install idevicerestore`` on Debian/Ubuntu/Zorin.
    """
    pass


class IdevicerestoreError(Exception):
    """@brief Raised when ``idevicerestore`` exits with a non-zero status.

    The message is the last non-empty line captured from stderr (usually
    prefixed with ``ERROR: `` by the binary itself), falling back to a
    generic message mentioning the exit code if stderr was empty.
    """
    pass


class IdevicerestoreCancelledError(Exception):
    """@brief Raised when the restore was cancelled via ``RestoreHandle.cancel()``."""
    pass


class RestoreStep(IntEnum):
    """@brief Mirrors the RESTORE_STEP_* enum from idevicerestore.h.

    Order matters: values must match the C enum exactly, since the binary
    reports the step as a bare integer over --plain-progress, not a name.
    """
    DETECT = 0
    PREPARE = 1
    UPLOAD_FS = 2
    VERIFY_FS = 3
    FLASH_FW = 4
    FLASH_BB = 5
    FUD = 6
    UPLOAD_IMG = 7


## Labels are NOOT's own wording for the GUI/CLI, not strings from idevicerestore
## itself (the binary does not name steps in --plain-progress mode, only numbers).
_STEP_LABELS = {
    RestoreStep.DETECT: "Detecting device",
    RestoreStep.PREPARE: "Preparing restore",
    RestoreStep.UPLOAD_FS: "Uploading filesystem",
    RestoreStep.VERIFY_FS: "Verifying filesystem",
    RestoreStep.FLASH_FW: "Flashing firmware",
    RestoreStep.FLASH_BB: "Flashing baseband",
    RestoreStep.FUD: "Finalizing update",
    RestoreStep.UPLOAD_IMG: "Uploading disk image",
}

_NUM_STEPS = len(RestoreStep)

_PROGRESS_LINE_RE = re.compile(r"^progress:\s+(\d+)\s+([\d.]+)\s*$")


@dataclass(frozen=True)
class RestoreProgress:
    """@brief A single progress update from idevicerestore.

    :ivar step: Coarse phase of the restore, per ``RestoreStep``.
    :ivar step_label: NOOT's own human-readable label for ``step`` (English,
        for CLI/GUI display) — not text emitted by idevicerestore itself.
    :ivar step_progress: Progress within the current step, 0-100.
    :ivar overall_progress: Estimated progress across the whole restore,
        0-100, computed as ``(step + step_progress/100) / num_steps * 100``.
        This is only an estimate: steps do not all take the same amount of
        time (UPLOAD_FS and FLASH_FW are typically much longer than DETECT),
        so it grows monotonically but not at a constant rate. Good enough to
        drive a real (non-indeterminate) progress bar; not a precise ETA.
    """
    step: RestoreStep
    step_label: str
    step_progress: float
    overall_progress: float


def _parse_progress_line(line: str) -> Optional[RestoreProgress]:
    match = _PROGRESS_LINE_RE.match(line)
    if match is None:
        return None

    raw_step, raw_step_progress = match.groups()
    try:
        step = RestoreStep(int(raw_step))
    except ValueError:
        ## Unknown step index: a future idevicerestore version added a step
        ## this module doesn't know about yet. Surface the update as best we
        ## can instead of dropping it silently or crashing the restore.
        step_progress = float(raw_step_progress)
        return RestoreProgress(
            step=RestoreStep.DETECT,
            step_label=f"Unknown step {raw_step}",
            step_progress=step_progress,
            overall_progress=step_progress / _NUM_STEPS,
        )

    step_progress = float(raw_step_progress)
    overall_progress = (int(step) + step_progress / 100.0) / _NUM_STEPS * 100.0
    return RestoreProgress(
        step=step,
        step_label=_STEP_LABELS[step],
        step_progress=step_progress,
        overall_progress=overall_progress,
    )


def is_idevicerestore_available() -> bool:
    """@brief Check whether the ``idevicerestore`` binary is installed and on PATH."""
    return shutil.which("idevicerestore") is not None


class RestoreHandle:
    """@brief A cancellable handle onto a running ``idevicerestore`` subprocess.

    Returned by ``flash_from_ipsw`` for advanced callers that need to cancel
    an in-progress restore (e.g. a "Cancel" button in the GUI). Most callers
    can ignore this and just ``await`` the coroutine ``flash_from_ipsw``
    returns directly.
    """

    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self._process = process
        self._cancelled = False

    async def cancel(self, timeout: float = 5.0) -> None:
        """@brief Request cancellation of the running restore.

        Sends SIGTERM first, giving idevicerestore ``timeout`` seconds to
        shut down its USB/network connections cleanly; escalates to SIGKILL
        only if it does not exit in time. Cancelling mid-flash can still
        leave the device in an inconsistent state (this is a limitation of
        interrupting any firmware restore, not specific to this wrapper) —
        prefer letting erase/update finish whenever possible.
        """
        if self._process.returncode is not None:
            return  # already exited on its own

        self._cancelled = True
        self._process.terminate()
        try:
            await asyncio.wait_for(self._process.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self._process.kill()
            await self._process.wait()


async def flash_from_ipsw(
    ipsw_path: str,
    udid: Optional[str],
    ecid: Optional[int],
    erase: bool,
    progress_callback: Optional[Callable[[RestoreProgress], None]] = None,
    restore_mode: bool = False,
    handle_out: Optional[list] = None,
) -> None:
    """@brief Flash or restore a device from an IPSW using the external idevicerestore binary.

    This is NOOT's sole engine for flashing/restoring firmware — it replaces
    the pymobiledevice3-based path entirely, for every device (pre-A7 and
    A7+ alike), not just the ones pymobiledevice3 cannot handle.

    :param ipsw_path: Path to a local ``.ipsw`` file or an extracted IPSW
        directory. Unlike ``idevice.open_ipsw``, idevicerestore does not
        accept a URL directly — download the file first if needed.
    :param udid: UDID of a normally-booted device. Mutually exclusive with
        ``ecid``. Per idevicerestore's own docs, this only works for
        normally-booted devices, not Recovery/DFU.
    :param ecid: ECID (as an int; hex or decimal are both fine at the CLI
        level, but this wrapper always passes it as hex) of a device already
        in Recovery/DFU/WTF. Mutually exclusive with ``udid``.
    :param erase: ``True`` for a factory-reset restore (data loss), ``False``
        to update in place preserving user data.
    :param progress_callback: Called synchronously with a ``RestoreProgress``
        for every progress line idevicerestore prints. Optional — omit it to
        just await completion without incremental updates.
    :param restore_mode: Pass ``True`` if the device is already stuck in
        Restore mode (maps to idevicerestore's ``--restore-mode``); this is
        distinct from Recovery/DFU and rare in practice (a previous restore
        attempt that failed partway through).
    :param handle_out: Optional empty list; if given, a ``RestoreHandle`` is
        appended to it as soon as the subprocess starts, letting the caller
        cancel the restore from another task while this coroutine is still
        running. Using a list instead of a return value keeps this an
        ``async def`` awaited straight through to completion, consistent
        with the rest of NOOT's idevice.py functions.
    :raises ValueError: If both or neither of ``udid``/``ecid`` are given.
    :raises IdevicerestoreNotInstalledError: If the binary is not on PATH.
    :raises IdevicerestoreError: If idevicerestore exits with a non-zero
        status (device not found, incompatible IPSW, signing server
        rejection, communication failure, etc. — see the exception message,
        taken from idevicerestore's own stderr output).
    :raises IdevicerestoreCancelledError: If ``RestoreHandle.cancel()`` was
        called before the process exited on its own.
    """
    if (udid is None) == (ecid is None):
        raise ValueError("Specifica esattamente uno tra udid ed ecid, non entrambi né nessuno.")

    if not is_idevicerestore_available():
        raise IdevicerestoreNotInstalledError(
            "idevicerestore non è installato. Installalo con: sudo apt install idevicerestore"
        )

    args = ["--plain-progress", "--no-input"]
    if erase:
        args.append("--erase")
    if udid is not None:
        args += ["--udid", udid]
    else:
        args += ["--ecid", f"0x{ecid:x}"]
    if restore_mode:
        args.append("--restore-mode")
    args.append(ipsw_path)

    process = await asyncio.create_subprocess_exec(
        "idevicerestore",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    handle = RestoreHandle(process)
    if handle_out is not None:
        handle_out.append(handle)

    stderr_lines: list[str] = []

    async def _consume_stdout() -> None:
        assert process.stdout is not None
        async for raw_line in process.stdout:
            line = raw_line.decode(errors="replace").rstrip("\n")
            if progress_callback is None:
                continue
            progress = _parse_progress_line(line)
            if progress is not None:
                progress_callback(progress)

    async def _consume_stderr() -> None:
        assert process.stderr is not None
        async for raw_line in process.stderr:
            stderr_lines.append(raw_line.decode(errors="replace").rstrip("\n"))

    await asyncio.gather(_consume_stdout(), _consume_stderr())
    returncode = await process.wait()

    if handle._cancelled:
        raise IdevicerestoreCancelledError("Il restore è stato annullato dall'utente.")

    if returncode != 0:
        last_error = next((l for l in reversed(stderr_lines) if l.strip()), None)
        if last_error is not None:
            raise IdevicerestoreError(last_error)
        raise IdevicerestoreError(f"idevicerestore è terminato con codice {returncode}.")
