import asyncio
import os
import plistlib
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Optional
 
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

async def get_connected_devices():
    """Ritorna lista di dispositivi con UDID e nome"""
    try:
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
    """Riassunto leggibile del dispositivo selezionato"""
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
    STARTED = auto()       # non era attivo, ora lo è
    FAILED = auto()         # non è stato possibile avviarlo

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
    """Sollevato quando si tenta un backup ma il device non ha l'encryption attiva."""
    pass
 
 
class IncrementalExcludeConflictError(Exception):
    """Sollevato quando si richiede --incremental insieme a --exclude.
 
    La libreria sottostante forza sempre un full backup quando il manifest deve
    essere "patchato" per applicare un filtro di esclusione (patch_manifest=True
    implica full=True). Piuttosto che eseguire silenziosamente un full backup
    quando l'utente ha chiesto esplicitamente un incrementale, preferiamo fermarci
    e segnalarlo chiaramente.
    """
    pass
 
 
class IncorrectBackupPasswordError(Exception):
    """Sollevato quando il device rifiuta la password fornita per un'operazione
    che la richiede (disable_backup_encryption, restore di un backup criptato, ecc.).
 
    pymobiledevice3 non espone un'eccezione dedicata per questo caso: il device
    risponde con un errore generico (PyMobileDevice3Exception / DeviceLink error)
    che qui viene reinterpretato nel contesto in cui una password errata è
    l'unica causa plausibile del fallimento.
    """
    pass
 
 
async def is_backup_encrypted(udid: str) -> bool:
    """True se il dispositivo è configurato per criptare i propri backup (WillEncrypt)."""
    lockdown = await create_using_usbmux(serial=udid)
    async with Mobilebackup2Service(lockdown) as mb2:
        return await mb2.get_will_encrypt()
 
 
async def enable_backup_encryption(udid: str, password: str) -> None:
    """Attiva l'encryption dei backup sul dispositivo impostando una nuova password.
 
    Va chiamato una sola volta (o quando si vuole cambiare password): l'impostazione
    resta valida sul device finché non viene esplicitamente disattivata.
    """
    lockdown = await create_using_usbmux(serial=udid)
    async with Mobilebackup2Service(lockdown) as mb2:
        await mb2.change_password(old="", new=password)
 
 
async def disable_backup_encryption(udid: str, password: str) -> None:
    """Disattiva l'encryption dei backup sul dispositivo (richiede la password attuale)."""
    lockdown = await create_using_usbmux(serial=udid)
    async with Mobilebackup2Service(lockdown) as mb2:
        await mb2.change_password(old=password, new="")
 
 
# ---------------------------------------------------------------------------
# Backup execution
# ---------------------------------------------------------------------------
 
# Mappa i nomi usati in --exclude ai preset già pronti in pymobiledevice3
EXCLUDABLE_CATEGORIES = {s.value: s for s in BackupSelection}
 
 
def _build_exclude_filter(categories: list[str]) -> Optional[BackupFilterCallback]:
    """Costruisce un filter_callback che ESCLUDE i file appartenenti alle categorie indicate.
 
    filter_callback in pymobiledevice3 ritorna True per i file da TENERE, quindi qui
    invertiamo la logica dei preset (che matchano cosa includere in quella categoria).
 
    Il callback viene invocato in due contesti diversi dalla libreria, con campi
    diversi popolati in BackupFile:
      - durante il transfer live: solo `device_name` è valorizzato
      - durante il pruning del manifest (patch_manifest=True): `domain` + `relative_path`
    Per coprire entrambi i casi controlliamo qualunque campo sia disponibile.
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
    """Esegue il backup del dispositivo.
 
    :param udid: UDID del device target.
    :param backup_dir: Cartella radice dove salvare il backup (verrà creata una
        sottocartella <udid> al suo interno, gestita direttamente dalla libreria).
    :param full: True per backup completo, False per incrementale (se non esiste
        ancora uno stato incrementale valido, la libreria forza comunque un full).
    :param exclude: Lista di categorie da escludere (valori validi: vedi
        EXCLUDABLE_CATEGORIES.keys()).
    :param password: Password di encryption del backup. Obbligatoria perché NOOT
        richiede sempre backup criptati.
    :param progress_callback: Chiamata con la percentuale di completamento (float).
    :raises EncryptionNotEnabledError: se il device non ha l'encryption attiva.
        L'utente deve prima lanciare il comando dedicato per abilitarla.
    :raises IncrementalExcludeConflictError: se full=False ed exclude non è vuoto
        (combinazione non supportata: vedi nota sulla classe).
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
 
 
def list_local_backups(backup_dir: Path) -> list[str]:
    """Ritorna la lista degli UDID per cui esiste un backup locale valido dentro backup_dir.
 
    Utile per popolare un menu "quale backup vuoi ripristinare" quando si gestiscono
    più device (es. backup di device diversi salvati nella stessa cartella radice).
    """
    if not backup_dir.exists():
        return []
 
    result = []
    for entry in backup_dir.iterdir():
        if not entry.is_dir():
            continue
        if all((entry / f).exists() for f in ("Info.plist", "Manifest.plist", "Status.plist")):
            result.append(entry.name)
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
 
async def erase_device(udid: str) -> None:
    """Ripristina il dispositivo allo stato di fabbrica, cancellando TUTTI i dati.
 
    Operazione irreversibile. La libreria sottostante (Mobilebackup2Service.erase_device)
    non richiede alcuna conferma né password: chiamarla esegue la cancellazione
    immediatamente. 
 
    :param udid: UDID del device da cancellare.

    """
 
    lockdown = await create_using_usbmux(serial=udid)
    async with Mobilebackup2Service(lockdown) as mb2:
        # backup_directory qui serve solo per il canale device_link (protocollo),
        # non viene scritto alcun backup reale durante un erase.
        await mb2.erase_device()

