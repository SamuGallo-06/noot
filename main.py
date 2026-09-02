import asyncio
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.usbmux import list_devices


async def get_connected_devices():
    """Ritorna lista di dispositivi con UDID e nome — per popolare un menu a tendina"""
    devices = await list_devices()
    result = []
    for dev in devices:
        udid = dev.serial
        lockdown = await create_using_usbmux(serial=udid)
        result.append({
            "udid": udid,
            "name": lockdown.short_info.get("DeviceName"),
        })
    return result


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


async def main():
    devices = await get_connected_devices()
    print("Dispositivi trovati:")
    for d in devices:
        print(f"  - {d['name']} ({d['udid']})")

    if devices:
        selected = devices[0]["udid"]  # qui poi ci metti la selezione da menu
        print("\nRiassunto:")
        summary = await get_device_summary(selected)
        for k, v in summary.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(main())