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
from pymobiledevice3.irecv import IRecv, Mode as IRecvMode
from pymobiledevice3.exceptions import (
    ConnectionFailedToUsbmuxdError,
    UserDeniedPairingError,
    PyMobileDevice3Exception,
    IRecvNoDeviceConnectedError,
    IRecvError,
)
from ipsw_parser.ipsw import IPSW
from pymobiledevice3.restore.device import Device
from pymobiledevice3.restore.base_restore import Behavior
from pymobiledevice3.restore.restore import Restore
from pymobiledevice3.services.mobilebackup2 import (
    Mobilebackup2Service,
    BackupFile,
    BackupSelection,
    BackupFilterCallback,
)
from pymobiledevice3.services.diagnostics import DiagnosticsService
import typer
import shutil


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

    typer.secho("usbmuxd is not running. Attempting to start it...", fg=typer.colors.YELLOW)
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

def delete_local_backup(backup_dir: Path, udid: str) -> None:
    """@brief Delete a local backup folder from disk.

    This operation is irreversible and does not touch any connected device:
    it only removes files under ``backup_dir``. No confirmation is requested
    here; the caller (CLI or GUI) is responsible for confirming with the user
    before calling this function.

    :param backup_dir: Root folder containing the ``<udid>/`` backup folders.
    :param udid: UDID of the backup to delete.
    :raises BackupNotFoundError: If no valid backup exists for ``udid`` in
        ``backup_dir``.
    """
    device_directory = backup_dir / udid

    if not all((device_directory / f).exists() for f in ("Info.plist", "Manifest.plist", "Status.plist")):
        raise BackupNotFoundError(
            f"Nessun backup valido trovato per '{udid}' in {backup_dir}. "
            f"Backup disponibili: {list_local_backups(backup_dir) or 'nessuno'}"
        )

    shutil.rmtree(device_directory)
 
 
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

## @brief Boot state detection (DFU / Recovery / WTF).
##
## This protocol is independent from lockdown/usbmuxd: a device in DFU or
## Recovery mode does not appear in ``list_devices()`` at all, because it does
## not run the lockdown daemon usbmuxd talks to. It only enumerates as a bare
## USB device with an Apple-specific product ID. Detecting it requires talking
## to libusb directly via ``pymobiledevice3.irecv.IRecv``, which is
## synchronous and blocking by nature (it wraps pyusb), so it is always run
## in a worker thread via ``asyncio.to_thread`` to avoid blocking the event loop.

class BootState(Enum):
    """@brief Coarse boot state of a device, independent of usbmuxd."""
    RECOVERY = auto()
    DFU = auto()
    ## "What The Fuck" mode: a rare, more bricked sibling of DFU, reachable
    ## e.g. after a failed baseband flash. Surfaced distinctly because it is
    ## not something the CLI should silently fold into DFU.
    WTF = auto()


def _classify_irecv_mode(mode: IRecvMode) -> BootState:
    if mode is IRecvMode.DFU_MODE:
        return BootState.DFU
    if mode is IRecvMode.WTF_MODE:
        return BootState.WTF
    ## Remaining values are RECOVERY_MODE_1..4, all covered by is_recovery.
    return BootState.RECOVERY


def _probe_irecv_device() -> Optional[dict]:
    """@brief Blocking libusb probe. Runs in a worker thread, never call directly from async code."""
    try:
        ## timeout=0: perform a single immediate scan instead of IRecv's
        ## default of blocking indefinitely until a device shows up.
        with IRecv(timeout=0) as irecv:
            info = {
                "state": _classify_irecv_mode(irecv.mode),
                "ecid": irecv.ecid,
                "serial": irecv.serial_number,
                "iboot_version": irecv.iboot_version,
            }
            ## product_type/hardware_model/display_name rely on a local static
            ## table (IRECV_DEVICES) that may lag behind brand-new hardware,
            ## so a lookup miss must not take down detection entirely.
            try:
                info["product_type"] = irecv.product_type
                info["hardware_model"] = irecv.hardware_model
                info["display_name"] = irecv.display_name
            except KeyError:
                info["product_type"] = None
                info["hardware_model"] = None
                info["display_name"] = None
            return info
    except IRecvNoDeviceConnectedError:
        return None


async def get_boot_state_device() -> Optional[dict]:
    """@brief Detect a single device currently in DFU, Recovery, or WTF mode.

    Unlike :func:`get_connected_devices`, this does not go through usbmuxd: a
    device stuck in one of these modes is invisible to usbmuxd entirely. This
    is why the GUI (which only lists normally-booted devices via
    ``get_connected_devices``) and the CLI need separate detection paths: the
    CLI must also surface devices in these states, e.g. to guide a user
    recovering a bricked device or about to flash firmware.

    :return: ``None`` if no device in DFU/Recovery/WTF is found (it may still
        be booted normally, or simply absent). Otherwise a dict with keys
        ``state`` (:class:`BootState`), ``ecid``, ``serial``,
        ``iboot_version``, ``product_type``, ``hardware_model``,
        ``display_name``. The last three may be ``None`` if the board/chip ID
        pair is not present in pymobiledevice3's static device table.
    :raises IRecvError: If more than one device in DFU/Recovery/WTF is
        connected simultaneously; ``IRecv`` itself refuses to disambiguate.
        This mirrors NOOT's one-device-at-a-time architecture.
    """
    return await asyncio.to_thread(_probe_irecv_device)


class RecoveryDeviceMismatchError(Exception):
    """@brief Raised when the ECID of the device in Recovery/DFU/WTF does not match the one requested."""
    pass


async def validate_flash_target(udid: Optional[str], ecid: Optional[int]) -> None:
    """@brief Confirm that an explicit flash target actually matches a connected device.

    Flashing is destructive and, unlike ``resolve_device_identifier``, never
    guesses or auto-selects a device: the caller must always supply exactly
    one of ``udid`` (device booted normally) or ``ecid`` (device already
    stuck in Recovery/DFU/WTF, e.g. after a failed update — obtain it via
    ``get_boot_state_device()`` / the CLI's ``list-dfu``). This function only
    verifies that identifier is real right now; it does not pick one itself.

    :param udid: Exact UDID of a normally-booted device. Mutually exclusive with ``ecid``.
    :param ecid: Exact ECID of a device already in Recovery/DFU/WTF. Mutually exclusive with ``udid``.
    :raises ValueError: If both or neither of ``udid``/``ecid`` are given.
    :raises DeviceNotFoundError: If ``udid`` does not match any connected device.
    :raises RecoveryDeviceMismatchError: If a device in Recovery/DFU/WTF is
        found but its ECID does not match ``ecid``.
    :raises IRecvError: If more than one device in Recovery/DFU/WTF is
        connected simultaneously; ``IRecv`` itself refuses to disambiguate.
    """
    if (udid is None) == (ecid is None):
        raise ValueError("Specifica esattamente uno tra udid ed ecid, non entrambi né nessuno.")

    if udid is not None:
        devices = await get_connected_devices()
        if not any(d["udid"] == udid for d in devices):
            available = ", ".join(d["udid"] for d in devices) or "nessuno"
            raise DeviceNotFoundError(
                f"Nessun device connesso con UDID '{udid}'. Device connessi: {available}"
            )
        return

    boot_state_device = await get_boot_state_device()
    if boot_state_device is None:
        raise DeviceNotFoundError(
            f"Nessun device in Recovery/DFU/WTF trovato con ECID {ecid:x}."
        )
    if boot_state_device["ecid"] != ecid:
        raise RecoveryDeviceMismatchError(
            f"Il device in {boot_state_device['state'].name} ha ECID "
            f"{boot_state_device['ecid']:x}, non {ecid:x}."
        )



## @brief Firmware flash tools (flash/restore a device from an IPSW).
##
## IPSW reading (``open_ipsw``, ``get_ipsw_file_info``) is handled by the
## separate ``ipsw_parser`` library (a pymobiledevice3 dependency, not part of
## it). Those two functions are plain blocking I/O (local zip reads, or
## ranged HTTP requests for a URL via ``RemoteZip``) with no ``await`` inside,
## so they stay synchronous on purpose — same reasoning as ``_probe_irecv_device``
## above. Only ``flash_from_ipsw`` is async, since it drives the actual
## restore protocol over the device connection.
 
def open_ipsw(file_path: str) -> IPSW:
    """@brief Open an IPSW file and return it.
 
    :param file_path: Path to a local IPSW file, an extracted IPSW directory,
        or an http(s) URL. See ``IPSW.create_from_path``.
    :raises FileNotFoundError: If ``file_path`` does not exist (local path only).
    :raises BadZipFile: If the file is not a valid IPSW/zip archive.
    """
    return IPSW.create_from_path(file_path)
 
 
def get_ipsw_file_info(source: IPSW) -> dict:
    """@brief Return a dict with the IPSW's version, build, and supported product types.
 
    :param source: An already-opened IPSW object.
    :return: A dict with keys ``product_version``, ``product_build_version``,
        ``supported_product_types``, ``build_major``.
    """
    manifest = source.build_manifest
 
    return {
        "product_version": manifest.product_version,               # "17.5.1"
        "product_build_version": manifest.product_build_version,   # "21F90"
        "supported_product_types": manifest.supported_product_types,  # ["iPhone10,3", "iPhone10,6", ...]
        "build_major": manifest.build_major,                       # 21 (int)
    }
 
 
class UnsupportedFirmwareFormatError(Exception):
    """@brief Raised when the target device predates Apple's Image4 firmware format.
 
    Devices before the A7 chip (iPhone 5s / iPad Air 1 / iPad mini 2 and
    later use Image4) rely on the older Image3 format instead. pymobiledevice3
    contains some Image3 tag-generation code (``TSSRequest.add_ap_img3_tags``)
    but gates it behind an unconditional Image4 check in
    ``BaseRestore.ensure_image4_supported()``, making that code path
    unreachable in practice — it appears unfinished/untested upstream rather
    than a deliberately supported feature. Attempting to bypass that guard
    risks bricking the device mid-flash with no confirmed-working fallback,
    so NOOT does not attempt it: flashing from IPSW is limited to A7+ devices.
    Backup, restore, and erase (which do not depend on Image3/Image4) are
    unaffected and still work on older hardware.
    """
    pass
 
 
async def flash_from_ipsw(
    udid: Optional[str],
    ecid: Optional[int],
    ipsw: IPSW,
    erase: bool,
) -> None:
    """@brief Flash or restore a device from an IPSW.
 
    :param udid: UDID of a normally-booted device. Required (and used) only
        when the device is not already in DFU/Recovery — ``ecid`` is ignored
        in that case.
    :param ecid: ECID of a device already in DFU/Recovery/WTF mode. Required
        (and used) only when the device is not reachable via usbmuxd; obtain
        it beforehand via ``get_boot_state_device()`` while the device was
        still connected, or let the caller resolve it themselves. May be
        ``None`` to accept the first device found in DFU/Recovery/WTF,
        regardless of identity.
    :param ipsw: Already-opened IPSW to flash, as returned by ``open_ipsw()``.
    :param erase: ``True`` for a factory-reset restore (data loss), ``False``
        to update in place preserving user data.
    :raises UnsupportedFirmwareFormatError: If the device predates Image4
        (pre-A7 hardware, e.g. iPad mini 1, iPhone 5c). See the exception's
        docstring for why this is a hard limitation, not a bug.
    :raises IRecvError: If more than one device in DFU/Recovery/WTF is found
        and ``ecid`` was not specific enough to disambiguate.
    :raises IRecvNoDeviceConnectedError: If no matching device shows up
        before ``IRecv`` gives up waiting.
    """
    if udid is not None:
        lockdown = await create_using_usbmux(serial=udid)
        device = Device(lockdown=lockdown)
    else:
        irecv = await asyncio.to_thread(IRecv, ecid=ecid)
        device = Device(irecv=irecv)
 
    if not await device.get_is_image4_supported():
        raise UnsupportedFirmwareFormatError(
            "This device does not support the Image4 firmware format "
            "(pre-A7 hardware). Flashing from IPSW is not supported; "
            "use backup/restore/erase instead."
        )
 
    await Restore(
        ipsw,
        device,
        behavior=Behavior.Erase if erase else Behavior.Update,
    ).update()