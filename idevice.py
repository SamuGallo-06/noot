from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.usbmux import list_devices
from pymobiledevice3.exceptions import ConnectionFailedToUsbmuxdError, UserDeniedPairingError
import os

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
        "build": info.get("BuildVersion"),
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


async def check_usbmuxd() -> bool:
    try:
        await list_devices()
        return True
    except ConnectionFailedToUsbmuxdError:
        return False