"""Ponte tra le coroutine asyncio di idevice.py e il mondo dei segnali Qt.

idevice.py e' interamente async (pymobiledevice3 lo richiede), ma Qt non ha
un suo event loop asyncio nativo in questo progetto. AsyncWorker esegue una
singola coroutine dentro un QThread dedicato, con un proprio event loop
asyncio locale al thread, ed espone il risultato/errore/progresso tramite
segnali Qt — cosi il codice in main_window.py resta semplice codice Qt
"normale" (connect/emit) e non deve mai gestire await direttamente.

Uso tipico in main_window.py:

    worker = AsyncWorker(idevice.run_backup, udid, backup_dir, full=True)
    worker.signals.progress.connect(self._on_backup_progress)
    worker.signals.finished.connect(self._on_backup_done)
    worker.signals.error.connect(self._on_backup_error)
    self._threadpool.start(worker)

Ogni chiamata "pesante" (backup, restore, erase, ...) deve passare da qui:
non vanno mai chiamate le funzioni di idevice.py direttamente dal thread
della GUI, altrimenti la finestra si blocca per tutta la durata dell'operazione.
"""
from __future__ import annotations

import asyncio
import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    """Segnali emessi da un AsyncWorker.

    Definiti in una classe QObject separata perche' QRunnable non eredita
    da QObject e quindi non puo' emettere segnali direttamente.
    """

    ## Emesso durante l'esecuzione con un valore 0.0-100.0. Non tutte le
    ## operazioni di idevice.py forniscono un progresso significativo.
    progress = Signal(float)

    ## Emesso alla conclusione con successo. Il payload e' il valore di
    ## ritorno della coroutine (spesso None, dato che molte funzioni di
    ## idevice.py non ritornano nulla).
    finished = Signal(object)

    ## Emesso se la coroutine solleva un'eccezione. Si passa l'istanza
    ## dell'eccezione stessa (non solo il messaggio) cosi il chiamante puo'
    ## fare isinstance() per distinguere es. RestorePasswordRequiredError
    ## da un errore generico.
    error = Signal(Exception)


class AsyncWorker(QRunnable):
    """Esegue una coroutine di idevice.py su un thread separato dalla GUI.

    :param coro_func: la funzione async da chiamare (es. idevice.run_backup).
        Non va passata gia' chiamata: AsyncWorker si occupa di invocarla con
        gli argomenti forniti dentro il proprio event loop.
    :param args: argomenti posizionali per coro_func.
    :param kwargs: argomenti nominali per coro_func. Se coro_func accetta un
        parametro ``progress_callback``, AsyncWorker lo inietta automaticamente
        per inoltrare il progresso tramite il segnale ``progress`` — non va
        passato esplicitamente in kwargs.
    """

    def __init__(self, coro_func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._coro_func = coro_func
        self._args = args
        self._kwargs = kwargs
        self.signals = WorkerSignals()

    def _emit_progress(self, value: float) -> None:
        # Chiamato dal thread del worker: Qt inoltra comunque il segnale al
        # thread giusto tramite la queued connection di default tra thread.
        self.signals.progress.emit(value)

    @Slot()
    def run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            kwargs = dict(self._kwargs)
            kwargs.setdefault("progress_callback", self._emit_progress)
            result = loop.run_until_complete(self._coro_func(*self._args, **kwargs))
            self.signals.finished.emit(result)
        except TypeError:
            # coro_func non accetta progress_callback: si ritenta senza.
            try:
                result = loop.run_until_complete(self._coro_func(*self._args, **self._kwargs))
                self.signals.finished.emit(result)
            except Exception as exc:  # noqa: BLE001 - da mostrare in UI cosi' com'e'
                traceback.print_exc()
                self.signals.error.emit(exc)
        except Exception as exc:  # noqa: BLE001 - da mostrare in UI cosi' com'e'
            traceback.print_exc()
            self.signals.error.emit(exc)
        finally:
            loop.close()
