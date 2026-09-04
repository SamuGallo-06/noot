from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.usbmux import list_devices
from pymobiledevice3.exceptions import ConnectionFailedToUsbmuxdError, UserDeniedPairingError
from pymobiledevice3.services.mobilebackup2 import BackupFile
import os
from pathlib import Path
from enum import Enum, auto
import asyncio

async def get_connected_devices():
    """Ritorna lista di dispositivi con UDID e nome — per popolare un menu a tendina"""
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
        "build": import asyncioinfo.get("BuildVersion"),
        "serial": info.get("SerialNumber"),
        "udid": info.get("UniqueDeviceID"),
        "storage_totale_gb": round(info.get("TotalDiskCapacity", 0) / (1024**3), 1),
        "storage_libero_gb": round(info.get("AmountDataAvailable", 0) / (1024**3), 1) if info.get("AmountDataAvailable") else None,
        "wifi_mac": info.get("WiFiAddress"),
        "bluetooth_mac": info.get("BluetoothAddress"),
    }
    return summary


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
    
async def execute_backup(backup_dir: Path):
    # Placeholder for backup logic
    print("Connessione al dispositivo in corso...")
    # TODO: Implement actual backup execution
    #lockdown = create_using_usbmux()
    pass