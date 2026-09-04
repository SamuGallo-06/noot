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

## @brief usbmuxd management and status checking.

def usbmuxd_socket_exists() -> bool:
    return os.path.exists("/var/run/usbmuxd")

## @brief Status returned by usbmuxd availability checks.
class UsbmuxdStatus(Enum):
    ## @brief usbmuxd is already running.
    OK = auto()
    ## @brief usbmuxd was started successfully.
    STARTED = auto()
    ## @brief usbmuxd could not be started.
    FAILED = auto()

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


## @brief Backup execution.

## @brief Backup encryption.

 
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
 
 
## @brief Backup execution helpers.
 
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

## @brief Backup restore.
 
class BackupNotFoundError(Exception):
    """@brief Raised when no valid local backup exists for the specified source UDID.

    The backup directory is missing ``Info.plist``, ``Manifest.plist``, or
    ``Status.plist``.
    """
    pass
 
 
class RestorePasswordRequiredError(Exception):
    """@brief Raised when an encrypted backup is restored without a password.
 
    In this case the underlying library only logs an error and returns without
    doing anything. Convert that condition into an explicit exception so NOOT
    does not report success when the restore never started.
    """
    pass
 
 
def list_local_backups(backup_dir: Path) -> list[dict[str, str | datetime | None]]:
    """@brief Return the UDID, name, and date of valid local backups.
 
    Useful for populating a backup selection menu when multiple devices are
    stored in the same root folder.
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
    """@brief Restore a local backup onto the specified device.

    :param udid: UDID of the target device currently connected.
    :param backup_dir: Root folder containing the ``<udid>/`` backup folders.
    :param source_udid: UDID of the backup to restore. If ``None``, it defaults
        to ``udid``. Specify it when restoring a backup onto a different device.
    :param password: Backup password, required when the backup is encrypted.
    :param restore_system_files: Restore system files as well.
    :param reboot_after: Reboot the device after the restore.
    :param keep_backup_copy: Keep a copy of the backup folder before restoring.
    :param restore_settings: Restore the device settings as well.
    :param remove_items_not_in_backup: Remove device items not present in the backup.
    :param skip_apps: Do not force application reinstallation after the restore.
    :param progress_callback: Callback receiving the completion percentage.
    :raises BackupNotFoundError: If no valid backup exists for ``source_udid``.
    :raises RestorePasswordRequiredError: If the backup is encrypted and the
        password is empty.
    :raises IncorrectBackupPasswordError: If the device rejects the password.
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
 
 
## @brief Erase device.
 
async def erase_device(
    udid: str,
    confirm_udid: str,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> None:
    """@brief Restore the device to factory settings by deleting all data.

    This operation is irreversible. The underlying library does not require
    confirmation or a password, so the caller must provide the UDID a second
    time as explicit confirmation.

    :param udid: UDID of the device to erase.
    :param confirm_udid: Must match ``udid`` exactly. This prevents accidental
        calls with an unintended device identifier.
    :param progress_callback: Callback receiving progress events, if the device
        provides them. Erase is typically fast and may provide few events.
    :raises ValueError: If ``confirm_udid`` does not match ``udid``.
    """
    if confirm_udid != udid:
        raise ValueError("confirm_udid non coincide con udid: operazione annullata per sicurezza.")
 
    lockdown = await create_using_usbmux(serial=udid)
    async with Mobilebackup2Service(lockdown) as mb2:
        ## Replicate the internal logic of Mobilebackup2Service.erase_device(),
        ## which does not expose a progress_callback in its public signature.
        with suppress(IncompleteReadError):
            async with mb2.device_link(Path(".")) as dl:
                await dl.send_process_message(
                    {"MessageName": "EraseDevice", "TargetIdentifier": mb2.lockdown.udid}
                )
                await dl.dl_loop(progress_callback=progress_callback or (lambda _: None))

## @brief Power control.

async def restart_device(udid: str) -> None:
    """@brief Restart the device (equivalent to powering it off and on).

    No confirmation or password is required. The device disconnects from the USB
    bus during the restart, interrupting any active NOOT operation on it.

    :raises PyMobileDevice3Exception: If the device rejects the request.
    """
    lockdown = await create_using_usbmux(serial=udid)
    async with DiagnosticsService(lockdown) as diagnostics:
        await diagnostics.restart()


async def shutdown_device(udid: str) -> None:
    """@brief Shut down the device.

    No confirmation or password is required. Unlike a restart, the device does
    not power on again automatically.

    :raises PyMobileDevice3Exception: If the device rejects the request.
    """
    lockdown = await create_using_usbmux(serial=udid)
    async with DiagnosticsService(lockdown) as diagnostics:
        await diagnostics.shutdown()
        
        
## @brief Diagnostics and logs.

class DeviceNotFoundError(Exception):
    """@brief Raised when the identifier does not match a connected device."""
    pass


class AmbiguousDeviceNameError(Exception):
    """@brief Raised when a device name matches multiple connected devices.

    This happens when two devices share the same ``DeviceName``. The caller must
    disambiguate them using an explicit UDID.
    """
    pass


async def resolve_device_identifier(identifier: str) -> str:
    """@brief Resolve a user-provided identifier (UDID or name) to the real UDID.

    If ``identifier`` exactly matches the UDID of a connected device, return it
    unchanged. Otherwise, interpret it as a case-insensitive device name.

    Intended for low- and medium-risk commands such as list, summary, backup,
    and enable-encryption. Do not use it for destructive commands such as erase,
    restore, and shutdown; those commands must request an explicit UDID.

    :param identifier: Exact UDID or case-insensitive device name.
    :raises DeviceNotFoundError: If no connected device matches.
    :raises AmbiguousDeviceNameError: If the name matches multiple devices.
    """
    devices = await get_connected_devices()

    ## Exact UDID match: ambiguity is impossible, so return immediately.
    for d in devices:
        if d["udid"] == identifier:
            return d["udid"]

    ## Otherwise, try a case-insensitive name match.
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


