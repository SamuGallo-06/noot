import asyncio
import os
import plistlib
from asyncio import IncompleteReadError
from contextlib import suppress
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Optional
from datetime import datetime
 
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.usbmux import list_devices
from pymobiledevice3.exceptions import (
    ConnectionFailedToUsbmuxdError,
    UserDeniedPairingError,
    PyMobileDevice3Exception,
)
from pymobiledevice3.services.mobilebackup2 import (
    Mobilebackup2Service,
    BackupFile,
    BackupSelection,
    BackupFilterCallback,
)
from pymobiledevice3.services.diagnostics import DiagnosticsService


async def get_connected_devices():
    """@brief Return the connected devices with their UDID and name."""
    try:
        print("Fetching connected devices...")
        devices = await list_devices()
        result = []
        for dev in devices:
            udid = dev.serial
            try:
                lockdown = await create_using_usbmux(serial=udid)
                result.append({
                    "udid": udid,
                    "name": lockdown.short_info.get("DeviceName"),
                })
            except UserDeniedPairingError:
                print(f"[Warning] Dispositivo {udid}: pairing non autorizzato. Ignorato.")
                continue
        return result
    except ConnectionFailedToUsbmuxdError:
        return []

async def get_device_summary(udid=None):
    """@brief Return a readable summary of the selected device."""
    lockdown = await create_using_usbmux(serial=udid)
    info = lockdown.all_values

    summary = {
        "nome": info.get("DeviceName"),
        "modello": info.get("ProductType"),
        "hardware": info.get("HardwareModel"),
        "ios_version": info.get("ProductVersion"),
        "build": info.get("BuildVersion"),
        "serial": info.get("SerialNumber"),
        "udid": info.get("UniqueDeviceID"),
        "storage_totale_gb": round(info.get("TotalDiskCapacity", 0) / (1024**3), 1),
        "storage_libero_gb": round(info.get("AmountDataAvailable", 0) / (1024**3), 1) if info.get("AmountDataAvailable") else None,
        "wifi_mac": info.get("WiFiAddress"),
        "bluetooth_mac": info.get("BluetoothAddress"),
    }
    return summary

############################################
#  usbmuxd management and status checking  #
############################################

def usbmuxd_socket_exists() -> bool:
    return os.path.exists("/var/run/usbmuxd")

class UsbmuxdStatus(Enum):
    OK = auto()
    STARTED = auto()       ## @brief usbmuxd was not running and is now running.
    FAILED = auto()         ## @brief usbmuxd could not be started.

async def ensure_usbmuxd_running(gui: bool = False) -> UsbmuxdStatus:
    auth_tool = "pkexec" if gui else "sudo"

    async def run_sys_cmd(cmd: list[str]) -> bool:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0

    if await check_usbmuxd():
        return UsbmuxdStatus.OK

    if not usbmuxd_socket_exists():
        await run_sys_cmd([auth_tool, "systemctl", "start", "usbmuxd"])
    else:
        await run_sys_cmd([auth_tool, "systemctl", "restart", "usbmuxd"])

    if await check_usbmuxd():
        return UsbmuxdStatus.STARTED
    return UsbmuxdStatus.FAILED

async def check_usbmuxd() -> bool:
    try:
        await list_devices()
        return True
    except ConnectionFailedToUsbmuxdError:
        return False


############################################
#  Backup execution                        #
############################################

# ---------------------------------------------------------------------------
# Backup encryption
# ---------------------------------------------------------------------------

 
class EncryptionNotEnabledError(Exception):
    """@brief Raised when a backup is attempted while device encryption is disabled."""
    pass
 
 
class IncrementalExcludeConflictError(Exception):
    """@brief Raised when ``--incremental`` is requested together with ``--exclude``.
 
    The underlying library always forces a full backup when the manifest must be
    patched to apply an exclusion filter (``patch_manifest=True`` implies
    ``full=True``). Instead of silently performing a full backup when the user
    explicitly requested an incremental one, stop and report the conflict.
    """
    pass
 
 
class IncorrectBackupPasswordError(Exception):
    """@brief Raised when the device rejects a password required by an operation.
 
    This covers operations such as ``disable_backup_encryption`` and restoring
    an encrypted backup. pymobiledevice3 does not expose a dedicated exception
    for this case: the device returns a generic error, which is reinterpreted
    here when an incorrect password is the only plausible cause.
    """
    pass
 
 
async def is_backup_encrypted(udid: str) -> bool:
    """@brief Return whether the device is configured to encrypt backups (WillEncrypt)."""
    lockdown = await create_using_usbmux(serial=udid)
    async with Mobilebackup2Service(lockdown) as mb2:
        return await mb2.get_will_encrypt()
 
 
async def enable_backup_encryption(udid: str, password: str) -> None:
    """@brief Enable backup encryption on the device with a new password.
 
    Call this once, or when changing the password. The setting remains active
    until it is explicitly disabled.
    """
    lockdown = await create_using_usbmux(serial=udid)
    async with Mobilebackup2Service(lockdown) as mb2:
        await mb2.change_password(old="", new=password)
 
 
async def disable_backup_encryption(udid: str, password: str) -> None:
    """@brief Disable backup encryption on the device using the current password."""
    lockdown = await create_using_usbmux(serial=udid)
    async with Mobilebackup2Service(lockdown) as mb2:
        try:
            await mb2.change_password(old=password, new="")
        except PyMobileDevice3Exception as e:
            raise IncorrectBackupPasswordError(
                "Il dispositivo ha rifiutato la password attuale del backup."
            ) from e


async def change_backup_encryption_password(
    udid: str,
    old_password: str,
    new_password: str,
) -> None:
    """@brief Change the backup encryption password on the device."""
    lockdown = await create_using_usbmux(serial=udid)
    async with Mobilebackup2Service(lockdown) as mb2:
        try:
            await mb2.change_password(old=old_password, new=new_password)
        except PyMobileDevice3Exception as e:
            raise IncorrectBackupPasswordError(
                "Il dispositivo ha rifiutato la password attuale del backup."
            ) from e
 
 
# ---------------------------------------------------------------------------
# Backup execution
# ---------------------------------------------------------------------------
 
## @brief Map the names used by ``--exclude`` to pymobiledevice3 presets.
EXCLUDABLE_CATEGORIES = {s.value: s for s in BackupSelection}
 
 
def _build_exclude_filter(categories: list[str]) -> Optional[BackupFilterCallback]:
    """@brief Build a filter callback that excludes files in the selected categories.
 
    ``filter_callback`` in pymobiledevice3 returns ``True`` for files to keep,
    so the preset matching logic is inverted here.
 
    The library invokes the callback in two contexts, with different
    ``BackupFile`` fields populated:
      - during live transfer: only ``device_name`` is populated;
      - during manifest pruning (``patch_manifest=True``): ``domain`` and
        ``relative_path`` are populated.
    Check every available field to cover both cases.
    """
    if not categories:
        return None
 
    selections = [EXCLUDABLE_CATEGORIES[c] for c in categories if c in EXCLUDABLE_CATEGORIES]
    if not selections:
        return None
 
    all_rules = [rule for selection in selections for rule in selection.rules()]
 
    def _filter(backup_file: BackupFile) -> bool:
        for rule in all_rules:
            if backup_file.domain and backup_file.relative_path:
                if rule.matches_manifest_entry(backup_file.domain, backup_file.relative_path):
                    return False
            if backup_file.device_name:
                if rule.matches_device_name(backup_file.device_name):
                    return False
        return True
 
    return _filter
 
 
async def run_backup(
    udid: str,
    backup_dir: Path,
    full: bool = True,
    exclude: Optional[list[str]] = None,
    password: str = "",
    progress_callback: Optional[Callable[[float], None]] = None,
) -> None:
    """@brief Back up the device.
 
    :param udid: UDID of the target device.
    :param backup_dir: Root folder for the backup. The library creates an
        ``<udid>`` subfolder inside it.
    :param full: ``True`` for a full backup, ``False`` for an incremental backup.
        The library still forces a full backup if no valid incremental state exists.
    :param exclude: Categories to exclude (see ``EXCLUDABLE_CATEGORIES.keys()``).
    :param password: Backup encryption password. Required because NOOT always
        requests encrypted backups.
    :param progress_callback: Callback receiving the completion percentage.
    :raises EncryptionNotEnabledError: If device encryption is disabled. Enable it
        first using the dedicated command.
    :raises IncrementalExcludeConflictError: If ``full=False`` and ``exclude`` is
        not empty; this combination is unsupported.
    """
    filter_callback = _build_exclude_filter(exclude or [])
 
    if not full and filter_callback is not None:
        raise IncrementalExcludeConflictError(
            "Non è possibile combinare --incremental con --exclude: applicare un filtro "
            "richiede di ripatchare il manifest, il che forza sempre un backup completo. "
            "Usa --full-backup con --exclude, oppure --incremental senza --exclude."
        )
 
    lockdown = await create_using_usbmux(serial=udid)
 
    async with Mobilebackup2Service(lockdown) as mb2:
        if not await mb2.get_will_encrypt():
            raise EncryptionNotEnabledError(
                "L'encryption dei backup non è attiva su questo dispositivo. "
                "Esegui prima 'noot enable-encryption' per impostare una password."
            )
 
        await mb2.backup(
            full=full,
            backup_directory=backup_dir,
            progress_callback=progress_callback or (lambda _: None),
            filter_callback=filter_callback,
            password=password,
            patch_manifest=filter_callback is not None,
        )

# ---------------------------------------------------------------------------
# Backup restore
# ---------------------------------------------------------------------------
 
class BackupNotFoundError(Exception):
    """Sollevato quando non esiste un backup locale valido per il source_udid indicato
    dentro backup_dir (mancano Info.plist / Manifest.plist / Status.plist)."""
    pass
 
 
class RestorePasswordRequiredError(Exception):
    """Sollevato quando il backup da ripristinare è criptato ma non è stata fornita
    una password.
 
    La libreria sottostante (Mobilebackup2Service.restore), in questo caso, si limita
    a loggare un errore e ritornare silenziosamente senza fare nulla — qui lo
    trasformiamo in un'eccezione esplicita per evitare che NOOT segnali "successo"
    quando in realtà il restore non è mai partito.
    """
    pass
 
 
def list_local_backups(backup_dir: Path) -> list[dict[str, str | datetime | None]]:
    """Ritorna UDID, nome e data dei backup locali validi dentro backup_dir.
 
    Utile per popolare un menu "quale backup vuoi ripristinare" quando si gestiscono
    più device (es. backup di device diversi salvati nella stessa cartella radice).
    """
    if not backup_dir.exists():
        return []
 
    result: list[dict[str, str | datetime | None]] = []
    for entry in backup_dir.iterdir():
        if not entry.is_dir():
            continue
        if all((entry / f).exists() for f in ("Info.plist", "Manifest.plist", "Status.plist")):
            with open(entry / "Info.plist", "rb") as file:
                info = plistlib.load(file)
            with open(entry / "Status.plist", "rb") as file:
                status = plistlib.load(file)
            result.append({
                "udid": entry.name,
                "device_name": info.get("Device Name") or info.get("Display Name"),
                "backup_date": status.get("Date"),
            })
    return result
 
 
def _backup_is_encrypted(backup_dir: Path, source_udid: str) -> bool:
    manifest_path = backup_dir / source_udid / "Manifest.plist"
    with open(manifest_path, "rb") as fd:
        manifest = plistlib.load(fd)
    return bool(manifest.get("IsEncrypted", False))
 
 
async def run_restore(
    udid: str,
    backup_dir: Path,
    source_udid: Optional[str] = None,
    password: str = "",
    restore_system_files: bool = False,
    reboot_after: bool = True,
    keep_backup_copy: bool = True,
    restore_settings: bool = True,
    remove_items_not_in_backup: bool = False,
    skip_apps: bool = False,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> None:
    """Ripristina un backup locale sul dispositivo indicato.
 
    :param udid: UDID del device SU CUI si esegue il ripristino (quello collegato ora).
    :param backup_dir: Cartella radice che contiene le sottocartelle <udid>/ dei backup.
    :param source_udid: UDID del backup DA ripristinare (chi ha prodotto quei dati).
        Se None, si assume coincida con `udid` (ripristino sullo stesso device che
        ha fatto il backup). Va specificato esplicitamente quando si vuole ripristinare
        il backup di un device su un device *diverso*.
    :param password: Password del backup, obbligatoria se il backup è criptato.
    :param restore_system_files: Ripristina anche i file di sistema.
    :param reboot_after: Riavvia il device al termine del ripristino.
    :param keep_backup_copy: Mantiene una copia della cartella di backup prima del ripristino.
    :param restore_settings: Ripristina anche le impostazioni del device.
    :param remove_items_not_in_backup: Rimuove dal device elementi non presenti nel backup.
    :param skip_apps: Non forzare la reinstallazione delle app dopo il ripristino.
    :param progress_callback: Chiamata con la percentuale di completamento (float).
    :raises BackupNotFoundError: se non esiste un backup valido per source_udid in backup_dir.
    :raises RestorePasswordRequiredError: se il backup è criptato e password è vuota.
    :raises IncorrectBackupPasswordError: se il device rifiuta la password fornita.
    """
    source = source_udid or udid
    device_directory = backup_dir / source
 
    if not all((device_directory / f).exists() for f in ("Info.plist", "Manifest.plist", "Status.plist")):
        raise BackupNotFoundError(
            f"Nessun backup valido trovato per '{source}' in {backup_dir}. "
            f"Backup disponibili: {list_local_backups(backup_dir) or 'nessuno'}"
        )
 
    if _backup_is_encrypted(backup_dir, source) and not password:
        raise RestorePasswordRequiredError(
            "Il backup selezionato è criptato: è necessaria la password per ripristinarlo."
        )
 
    lockdown = await create_using_usbmux(serial=udid)
    async with Mobilebackup2Service(lockdown) as mb2:
        try:
            await mb2.restore(
                backup_directory=backup_dir,
                system=restore_system_files,
                reboot=reboot_after,
                copy=keep_backup_copy,
                settings=restore_settings,
                remove=remove_items_not_in_backup,
                password=password,
                source=source,
                progress_callback=progress_callback or (lambda _: None),
                skip_apps=skip_apps,
            )
        except PyMobileDevice3Exception as e:
            raise IncorrectBackupPasswordError(
                "Il dispositivo ha rifiutato la password fornita per il backup."
            ) from e
 
 
###################################
##       Erase Device            ##
###################################
 
async def erase_device(
    udid: str,
    confirm_udid: str,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> None:
    """Ripristina il dispositivo allo stato di fabbrica, cancellando TUTTI i dati.
 
    Operazione irreversibile. La libreria sottostante (Mobilebackup2Service.erase_device)
    non richiede alcuna conferma né password: chiamarla esegue la cancellazione
    immediatamente. Per questo qui pretendiamo che il chiamante ripassi l'UDID una
    seconda volta come conferma esplicita (oltre a qualsiasi conferma interattiva
    che il layer CLI/GUI deciderà di chiedere all'utente).
 
    :param udid: UDID del device da cancellare.
    :param confirm_udid: Deve essere identico a `udid`. Serve a prevenire chiamate
        automatizzate o accidentali con un UDID diverso da quello effettivamente
        inteso (es. copia-incolla errato, variabile sbagliata nel chiamante).
    :param progress_callback: Chiamata con la percentuale di completamento (float),
        se il device invia eventi di progresso durante l'operazione. L'erase è
        tipicamente rapido: potrebbe non arrivare granularità utile.
    :raises ValueError: se confirm_udid non coincide con udid.
    """
    if confirm_udid != udid:
        raise ValueError("confirm_udid non coincide con udid: operazione annullata per sicurezza.")
 
    lockdown = await create_using_usbmux(serial=udid)
    async with Mobilebackup2Service(lockdown) as mb2:
        # Replichiamo qui la logica interna di Mobilebackup2Service.erase_device(),
        # che non espone un progress_callback nella sua firma pubblica.
        with suppress(IncompleteReadError):
            async with mb2.device_link(Path(".")) as dl:
                await dl.send_process_message(
                    {"MessageName": "EraseDevice", "TargetIdentifier": mb2.lockdown.udid}
                )
                await dl.dl_loop(progress_callback=progress_callback or (lambda _: None))

###################################
##       Power Control           ##
###################################

async def restart_device(udid: str) -> None:
    """Riavvia il dispositivo (equivalente a spegnimento + riaccensione).

    Non richiede conferma né password: l'operazione parte non appena chiamata.
    Il device si disconnette dal bus USB durante il riavvio; eventuali operazioni
    NOOT in corso su quel device (backup, restore) verranno interrotte.

    :raises PyMobileDevice3Exception: se il device rifiuta la richiesta.
    """
    lockdown = await create_using_usbmux(serial=udid)
    async with DiagnosticsService(lockdown) as diagnostics:
        await diagnostics.restart()


async def shutdown_device(udid: str) -> None:
    """Spegne il dispositivo.

    Non richiede conferma né password: l'operazione parte non appena chiamata.
    A differenza del riavvio, il device NON si riaccende da solo: per tornare
    a usarlo servirà tenere premuto il tasto fisico di accensione.

    :raises PyMobileDevice3Exception: se il device rifiuta la richiesta.
    """
    lockdown = await create_using_usbmux(serial=udid)
    async with DiagnosticsService(lockdown) as diagnostics:
        await diagnostics.shutdown()
        
        
#########################################
##       Diagnostics / Logs           ##
#########################################

class DeviceNotFoundError(Exception):
    """Sollevato quando l'identificatore fornito non corrisponde a nessun device connesso."""
    pass


class AmbiguousDeviceNameError(Exception):
    """Sollevato quando un nome (non UDID) corrisponde a più di un device connesso.

    Capita se due device condividono lo stesso DeviceName (es. entrambi chiamati
    "iPhone" perché non rinominati dall'utente). In questo caso non possiamo
    scegliere per lui: deve disambiguare con l'UDID esplicito.
    """
    pass


async def resolve_device_identifier(identifier: str) -> str:
    """Risolve un identificatore fornito dall'utente (UDID o nome) nell'UDID reale.

    Se `identifier` corrisponde esattamente all'UDID di un device connesso, viene
    ritornato invariato (nessuna chiamata aggiuntiva necessaria). Altrimenti viene
    interpretato come nome (case-insensitive) e cercato tra i device connessi.

    Pensata per comandi a basso/medio rischio (list, summary, backup,
    enable-encryption) dove la comodità del nome ha senso. NON usare per comandi
    distruttivi (erase, restore, shutdown): lì l'UDID esplicito va richiesto
    direttamente, senza risoluzione automatica.

    :param identifier: UDID esatto oppure nome del device (case-insensitive).
    :raises DeviceNotFoundError: se nessun device connesso corrisponde.
    :raises AmbiguousDeviceNameError: se il nome corrisponde a più device.
    """
    devices = await get_connected_devices()

    # Match esatto per UDID: nessuna ambiguità possibile, ritorna subito
    for d in devices:
        if d["udid"] == identifier:
            return d["udid"]

    # Altrimenti prova per nome, case-insensitive
    matches = [d for d in devices if (d.get("name") or "").lower() == identifier.lower()]

    if not matches:
        available = ", ".join(f"{d.get('name', 'Unknown')} ({d['udid']})" for d in devices) or "nessuno"
        raise DeviceNotFoundError(
            f"Nessun device trovato per '{identifier}'. Device connessi: {available}"
        )

    if len(matches) > 1:
        raise AmbiguousDeviceNameError(
            f"Più device si chiamano '{identifier}': "
            f"{', '.join(d['udid'] for d in matches)}. Specifica l'UDID esplicito."
        )

    return matches[0]["udid"]


