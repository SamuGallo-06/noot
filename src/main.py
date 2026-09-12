import asyncio
from functools import wraps
from pathlib import Path
import sys
from typing import Annotated, Optional
 
from platformdirs import user_data_dir
import typer
import click

from rich.console import Console
from rich.table import Table

from PySide6.QtWidgets import QApplication
 
import asyncio
from functools import wraps
from pathlib import Path
import sys
from typing import Annotated, Optional
 
from platformdirs import user_data_dir
import typer
import click
 
from rich.console import Console
from rich.table import Table
 
from PySide6.QtWidgets import QApplication
 
from idevice import (
    check_usbmuxd,
    get_connected_devices,
    get_device_summary,
    ensure_usbmuxd_running,
    UsbmuxdStatus,
    is_backup_encrypted,
    enable_backup_encryption,
    disable_backup_encryption,
    change_backup_encryption_password,
    run_backup,
    EncryptionNotEnabledError,
    IncrementalExcludeConflictError,
    EXCLUDABLE_CATEGORIES,
    IncorrectBackupPasswordError,
    run_restore,
    erase_device,
    list_local_backups,
    BackupNotFoundError,
    RestorePasswordRequiredError,
    PyMobileDevice3Exception,
    DeviceNotFoundError,
    AmbiguousDeviceNameError,
    resolve_device_identifier,
    restart_device,
    shutdown_device,
    get_boot_state_device,
    IRecvError,
    open_ipsw,
    get_ipsw_file_info,
    flash_from_ipsw,
    validate_flash_target,
    RecoveryDeviceMismatchError,
    UnsupportedFirmwareFormatError,
)
 
# Importing UI
from gui.main_window import MainWindow


# Importing UI
from gui.main_window import MainWindow

VERSION="1.0.0"

MAX_PASSWORD_ATTEMPTS = 3

DEFAULT_BACKUP_DIR = Path(user_data_dir("noot", "SamuGallo-06")) / "backups"

app = typer.Typer(
    help="NOOT - iOS device management and backup utility",
    no_args_is_help=True,
)

console = Console()

def coro(f):
    """Decorator to run async functions inside synchronous Typer commands."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

def version_callback():
    typer.echo(f"NOOT version: {VERSION}")
    raise typer.Exit()

def launch_gui():
    """Launch the graphical user interface."""
    app = QApplication(sys.argv)
    app.setApplicationName("Noot")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    gui: Annotated[
        bool,
        typer.Option("--gui", "-g", help="Launch GUI interface"),
    ] = False,
    version: Annotated[
        bool,
        typer.Option("--version", "-v", help="Display the current version")
    ] = False,
):
    """Global entry point: intercepts --gui or triggers interactive mode when no command is provided."""
    if gui:
        typer.echo("Launching graphical user interface...")
        launch_gui()
        raise typer.Exit()
    
    if version:
        version_callback()

    # Fallback to interactive mode if no CLI arguments/commands are supplied
    if ctx.invoked_subcommand is None:
        typer.echo("No command provided. use --help for usage information.")
        raise typer.Exit()


## Helper function to resolve device name or UDID to a valid UDID, with error handling and user feedback.
async def resolve_name(name_or_udid: str) -> str:
    try:
        udid = await resolve_device_identifier(name_or_udid)
    except DeviceNotFoundError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except AmbiguousDeviceNameError as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
    return udid

async def ensure_usbmuxd_or_exit(gui: bool = False):
    """@brief Wrap ensure_usbmuxd_running and map its status to CLI output and exit codes."""
    status = await ensure_usbmuxd_running(gui=gui)
    if status == UsbmuxdStatus.STARTED:
        typer.secho("usbmuxd was not running and has been started.", fg=typer.colors.GREEN)
    elif status == UsbmuxdStatus.FAILED:
        typer.secho(
            "Error: usbmuxd is unreachable and could not be started automatically.\n"
            "Try manually: sudo systemctl start usbmuxd",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

## @name Commands
## @{

@app.command("list")
@coro
async def list_devices():
    """List all connected iOS devices."""
    status = await ensure_usbmuxd_running()
    if status == UsbmuxdStatus.FAILED:
        typer.secho("Error: usbmuxd is unreachable.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    elif status == UsbmuxdStatus.STARTED:
        typer.secho("usbmuxd was restarted successfully.", fg=typer.colors.GREEN)

    if not await check_usbmuxd():
        typer.secho("Error: usbmuxd is unreachable.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    devices = await get_connected_devices()
    if not devices:
        typer.echo("No devices detected.")
        return

    typer.secho("Connected devices:", bold=True)
    table = Table()
    table.add_column("Name", style="cyan")
    table.add_column("UDID", style="magenta")
    for d in devices:
        name = d.get("name", "Unknown")
        udid = d.get("udid")
        table.add_row(name, udid)
    console.print(table)

@app.command("list-dfu")
@coro
async def list_dfu():
    """Check for a device in DFU, Recovery, or WTF mode (single instant check).

    Unlike ``list``, this does not go through usbmuxd: devices in these modes
    are invisible to it. Useful before a firmware flash, or while waiting for
    a device to enter DFU (re-run the command until it shows up).
    """
    try:
        device = await get_boot_state_device()
    except IRecvError as e:
        ## More than one device in DFU/Recovery/WTF at once: IRecv refuses to
        ## disambiguate them, consistent with NOOT's one-device-at-a-time
        ## architecture for destructive operations.
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        typer.secho(
            "Multiple devices in DFU/Recovery/WTF mode detected. "
            "Disconnect all but one and try again.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=1)

    if device is None:
        typer.echo("No device in DFU/Recovery/WTF mode detected.")
        return

    label = device["state"].name.replace("_", " ").title()
    typer.secho(f"Device in {label} mode:", bold=True, fg=typer.colors.YELLOW)
    table = Table(show_header=False)
    table.add_row("Model", device.get("display_name") or "Unknown")
    table.add_row("ECID", f"{device['ecid']:x}")
    table.add_row("Serial", device.get("serial") or "Unknown")
    table.add_row("iBoot version", device.get("iboot_version") or "Unknown")
    console.print(table)

@app.command("summary")
@coro
async def summary(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help="Device UDID or name (e.g. 'iPhone 5c'). Use 'noot list' to see options.",
            prompt="Enter device UDID or name",
        ),
    ],
):
    """Display detailed hardware and system info for a specific device."""
    udid = await resolve_name(udid)
    
    status = await ensure_usbmuxd_running()
    if status == UsbmuxdStatus.FAILED:
        typer.secho("Error: usbmuxd is unreachable.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    elif status == UsbmuxdStatus.STARTED:
        typer.secho("usbmuxd was restarted successfully.", fg=typer.colors.GREEN)

    info = await get_device_summary(udid)
    if not info:
        typer.secho(
            f"Error: Unable to fetch summary for device {udid}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    typer.secho(f"Device Summary [{udid}]:", bold=True)
    for k, v in info.items():
        typer.echo(f"  {k}: {v}")

@app.command("enable-encryption")
@coro
async def enable_encryption(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help="Device UDID or name. Use 'noot list' to see options.",
            prompt="Enter device UDID or name",
        ),
    ],
):
    
    """Enable backup encryption on the device by setting a new backup password.
 
    NOOT always performs encrypted backups, so this must be run once before the
    first backup (unless encryption is already enabled on the device, e.g. via
    a previous iTunes/Finder pairing).
    """
    
    udid = await resolve_name(udid)
    await ensure_usbmuxd_or_exit()
 
    if await is_backup_encrypted(udid):
        typer.secho("Backup encryption is already enabled on this device.", fg=typer.colors.GREEN)
        return
 
    typer.secho(
        "This password protects your backups. Passsword must be at least 8 characters long and contain both letters and numbers and special characters. Store it safely: it cannot be recovered, and you will need it to restore or read this device's backups.",
        fg=typer.colors.YELLOW,
    )
    
    typer.confirm("Do you want to enable encryption?")
    
    password = typer.prompt(
        text="Choose a password",
        default=None,
        hide_input=True,       
        confirmation_prompt=True,
        type=str,                
    )
    
    ## Handle password errors.
    if(password is None):
        typer.secho("Error: Password cannot be empty.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if(password.strip() == ""):
        typer.secho("Error: Password cannot be empty or whitespace.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    if len(password) < 4:
        typer.secho("Error: Password must be at least 4 characters long.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    """if(not any(char.isdigit() for char in password) or
       not any(char.isalpha() for char in password) or
       not any(not char.isalnum() for char in password)):
        typer.secho("Error: Password must contain both letters and numbers and special characters.", fg=typer.colors.RED)
        raise typer.Exit(code=1)"""
    
    ## Enable backup encryption.
    
    await enable_backup_encryption(udid, password)
    typer.secho("Backup encryption enabled successfully.", fg=typer.colors.GREEN)


@app.command("change-encryption-password")
@coro
async def change_encryption_password(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help="Device UDID or name. Use 'noot list' to see options.",
            prompt="Enter device UDID or name",
        ),
    ],
):
    """Change the current backup encryption password on the device."""
    udid = await resolve_name(udid)
    await ensure_usbmuxd_or_exit()

    if not await is_backup_encrypted(udid):
        typer.secho("Error: backup encryption is not enabled on this device.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    old_password = typer.prompt("Current backup password", hide_input=True)
    new_password = typer.prompt(
        "New backup password",
        hide_input=True,
        confirmation_prompt=True,
    )
    if not new_password.strip():
        typer.secho("Error: Password cannot be empty or whitespace.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if len(new_password) < 4:
        typer.secho("Error: Password must be at least 4 characters long.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    try:
        await change_backup_encryption_password(udid, old_password, new_password)
    except IncorrectBackupPasswordError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho("Backup encryption password changed successfully.", fg=typer.colors.GREEN)
  
@app.command("disable-encryption")
@coro
async def disable_encryption(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help="Device UDID or name. Use 'noot list' to see options.",
            prompt="Enter device UDID or name",
        ),
    ],
):
    """Disable backup encryption on the device (requires the current backup password)."""
    udid = await resolve_name(udid)
    await ensure_usbmuxd_or_exit()
 
    if not await is_backup_encrypted(udid):
        typer.secho("Backup encryption is already disabled on this device.", fg=typer.colors.GREEN)
        return
 
    for attempt in range(1, MAX_PASSWORD_ATTEMPTS + 1):
        password = typer.prompt("Current backup password", hide_input=True)
        try:
            await disable_backup_encryption(udid, password)
        except IncorrectBackupPasswordError:
            remaining = MAX_PASSWORD_ATTEMPTS - attempt
            if remaining > 0:
                typer.secho(
                    f"Incorrect password. {remaining} attempt(s) remaining.",
                    fg=typer.colors.RED,
                )
                continue
            typer.secho("Error: too many incorrect attempts.", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        else:
            typer.secho("Backup encryption disabled.", fg=typer.colors.GREEN)
            return
        
@app.command("list-backups")
@coro
async def list_backups(
    backup_dir: Annotated[
        Path,
        typer.Option(
            "--backup-dir",
            "-d",
            help="Folder containing local backups",
        ),
    ] = DEFAULT_BACKUP_DIR,
):
    """List local backups available in the backup folder."""
    backups = list_local_backups(backup_dir)
    if not backups:
        typer.echo(f"No backups found in {backup_dir}.")
        return
 
    typer.secho(
        f"{len(backups)} Backup{"s" if len(backups) > 1 else ""} found in {backup_dir}:", bold=True
    )
        
    table = Table()

    ## Define the table columns (style, alignment, and width).
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Device Name")
    table.add_column("UDID", justify="center")
    table.add_column("Date", justify="right")

    for i, b in enumerate(backups):  
        name = b["device_name"] or "Unknown device"
        date = b["backup_date"] or "Unknown date"
        udid = b['udid']
        table.add_row(str(i), str(name), str(udid), str(date))

    console.print(table)

@app.command("backup")
@coro
async def backup(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help="Device UDID or name. Use 'noot list' to see options.",
            prompt="Enter device UDID or name",
        ),
    ],
    backup_dir: Annotated[
        Path,
        typer.Option(
            "--backup-dir",
            "-d",
            help="Destination folder for backup files",
        ),
    ] = DEFAULT_BACKUP_DIR,
    full_backup: Annotated[
        bool,
        typer.Option(
            "--full-backup",
            "-fb",
            help="Perform Full Backup"
        ),
    ] = False,
    exclude: Annotated[
        Optional[list[str]],
        typer.Option(
            "--exclude",
            "-e",
            click_type=click.Choice(list(EXCLUDABLE_CATEGORIES.keys())),  # pyright: ignore[reportArgumentType]
            help="Category to exclude from the backup. Repeatable.",
        ),
    ] = None,
    ):
    """Run a local backup for the specified device."""
    
    udid = await resolve_name(udid)
    
    status = await ensure_usbmuxd_running()
    if status == UsbmuxdStatus.FAILED:
        typer.secho("Error: usbmuxd is unreachable.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    elif status == UsbmuxdStatus.STARTED:
        typer.secho("usbmuxd was restarted successfully.", fg=typer.colors.GREEN)
        
    backup_dir.mkdir(parents=True, exist_ok=True)

    if not await is_backup_encrypted(udid):
        typer.secho(
            "Error: backup encryption is not enabled on this device.\n"
            "Run 'noot enable-encryption --udid ...' first.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    typer.secho(
        "This backup will be encrypted. Please enter "
        "recovered, and you'll need it to restore or read this backup later.",
        fg=typer.colors.YELLOW,
    )
    password = typer.prompt("Backup password", hide_input=True)
    
    typer.secho(f"Starting {'full' if full_backup else 'incremental'} backup", bold=True)
    typer.echo(f"Device: {udid}")
    typer.echo(f"Destination: {backup_dir}")
    if exclude:
        typer.echo(f"Excluding: {', '.join(exclude)}")
    typer.echo("Keep the device connected and unlocked until the backup finishes.\n")
    
    last_percent = 0.0
 
    with typer.progressbar(length=100, label="Backing up") as progress:
        def on_progress(percent: float) -> None:
            nonlocal last_percent
            delta = max(0.0, percent - last_percent)
            if delta:
                progress.update(delta) #type: ignore
                last_percent = percent
 
        try:
            await run_backup(
                udid=udid,
                backup_dir=backup_dir,
                full=full_backup,
                exclude=exclude,
                password=password,
                progress_callback=on_progress,
            )
        except EncryptionNotEnabledError as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        except IncrementalExcludeConflictError as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        except IncorrectBackupPasswordError as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
 
    typer.secho("Backup completed successfully.", fg=typer.colors.GREEN)

@app.command("restore")
@coro
async def restore(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help="Target iOS device UDID (the device connected now, that will receive the restore).",
            prompt="Enter device UDID",
        ),
    ],
    source_udid: Annotated[
        Optional[str],
        typer.Option(
            "--source-udid",
            "-s",
            help=(
                "UDID of the backup to restore, if different from the target device. "
                "Defaults to the target device's own UDID (restore its own latest backup). "
                "Use 'noot list-backups' to see what's available."
            ),
        ),
    ] = None,
    backup_dir: Annotated[
        Path,
        typer.Option(
            "--backup-dir",
            "-d",
            help="Folder containing local backups",
        ),
    ] = DEFAULT_BACKUP_DIR,
    remove_items_not_in_backup: Annotated[
        bool,
        typer.Option(
            "--remove-extra-data/--keep-extra-data",
            help=(
                "Remove data on the device that isn't present in the backup "
                "(mirror restore). Default: keep extra data untouched."
            ),
        ),
    ] = False,
):
    """Restore a local backup onto the connected device."""
    
    udid = await resolve_name(udid)
    
    status = await ensure_usbmuxd_running()
    if status == UsbmuxdStatus.FAILED:
        typer.secho("Error: usbmuxd is unreachable.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    elif status == UsbmuxdStatus.STARTED:
        typer.secho("usbmuxd was restarted successfully.", fg=typer.colors.GREEN)
 
    ## If omitted, the source is the target device by default.
    source = source_udid or udid
 
    typer.secho("Restore backup", bold=True)
    typer.echo(f"Target device: {udid}")
    if source != udid:
        typer.secho(
            f"⚠ You are restoring a backup from a DIFFERENT device ({source}) "
            f"onto this one ({udid}).",
            fg=typer.colors.YELLOW,
        )
    else:
        typer.echo(f"Backup source: {source} (same as target)")
    typer.echo(f"Backup location: {backup_dir}")
 
    warning_lines = [
        "\nRestoring will overwrite existing data on the target device with the "
        "contents of this backup. This cannot be undone.",
    ]
    if remove_items_not_in_backup:
        warning_lines.append(
            "⚠ --remove-extra-data is enabled: any data on the device NOT present "
            "in this backup will also be deleted."
        )
    typer.secho("\n".join(warning_lines), fg=typer.colors.YELLOW)
    typer.confirm("Do you want to continue?", abort=True)
    
    typer.secho(
        "The device will restart automatically once the restore is complete. "
        "Keep it connected until then.",
        fg = typer.colors.BLUE
    )
 
    ## Check that the backup exists before requesting the password, so the user
    ## does not enter a password unnecessarily after specifying a wrong UDID.
    if not (backup_dir / source).exists():
        available = list_local_backups(backup_dir)
        typer.secho(f"Error: no backup found for '{source}' in {backup_dir}.", fg=typer.colors.RED)
        if available:
            typer.echo("Available backups:")
            for b in available:
                name = b["device_name"] or "Unknown device"
                typer.echo(f"  • {name} (UDID: {b['udid']})")
        raise typer.Exit(code=1)

    password = typer.prompt("Backup password (leave blank if not encrypted): ", hide_input=True)
 
    typer.secho(
        "\nFor safety reasons, please confirm you want to restore this device from a backup.",
        fg=typer.colors.RED,
        bold=True,
    )
    typed = typer.prompt(f"Type the device UDID ({udid}) to confirm the restore")
    if typed != udid:
        typer.secho("UDID does not match. Restore cancelled.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
 
    last_percent = 0.0
 
    with typer.progressbar(length=100, label="Restoring backup") as progress:
        def on_progress(percent: float) -> None:
            nonlocal last_percent
            delta = max(0.0, percent - last_percent)
            if delta:
                progress.update(delta)  # type: ignore
                last_percent = percent
 
        try:
            await run_restore(
                udid=udid,
                backup_dir=backup_dir,
                source_udid=source_udid,
                password=password,
                remove_items_not_in_backup=remove_items_not_in_backup,
                progress_callback=on_progress,
            )
        except BackupNotFoundError as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        except RestorePasswordRequiredError as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        except IncorrectBackupPasswordError as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
 
    typer.secho("Backup restored successfully.", fg=typer.colors.GREEN)

@app.command("delete")
@coro
async def delete(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help="Target iOS device UDID",
            prompt="Enter device UDID",
        ),
    ],
    backup_dir: Annotated[
        Path,
        typer.Option(
            "--backup-dir",
            "-d",
            help="Destination folder for backup files",
        ),
    ] = DEFAULT_BACKUP_DIR, 
):
    """Delete a local backup for the specified device UDID."""
    
    udid = await resolve_name(udid)

    backups = list_local_backups(backup_dir)
    backup_to_delete = next((b for b in backups if b["udid"] == udid), None)
    if not backup_to_delete:
        typer.secho(f"No backup found for UDID {udid} in {backup_dir}.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho(
        f"Are you sure you want to delete the backup for device '{backup_to_delete['device_name']}' (UDID: {udid})?",
        fg=typer.colors.YELLOW,
    )
    typer.confirm("This action cannot be undone. Continue?", abort=True)

    try:
        backup_path = Path(backup_dir) / udid
        if backup_path.exists():
            for item in backup_path.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    import shutil
                    shutil.rmtree(item)
            backup_path.rmdir()
            typer.secho(f"Backup for UDID {udid} deleted successfully.", fg=typer.colors.GREEN)
        else:
            typer.secho(f"Backup directory {backup_path} does not exist.", fg=typer.colors.RED)
            raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"Error deleting backup: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)



@app.command("erase")
@coro
async def erase(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help="Target iOS device UDID",
            prompt="Enter device UDID",
        ),
    ],
):
    """Erase all data on the specified iOS device, restoring it to factory settings."""
    
    udid = await resolve_name(udid)
    
    await ensure_usbmuxd_or_exit()
 
    typer.secho(
        "This operation will completely erase all data, settings, apps and "
        "personal files on the device, restoring it to its factory settings.\n",
        fg=typer.colors.YELLOW,
        bold=True,
    )
    typer.echo(
        "Before continuing, on the device:\n"
        "  1. Make sure the battery is charged at least 50%.\n"
        "  2. Turn off Find My (Settings > [Your Name] > Find My > Find My iPhone/iPad, "
        "and turn it off).\n"
        "  3. Keep the device connected via USB and do not disconnect it during the process.\n"
    )
    typer.confirm("Have you completed the steps above and want to continue?", abort=True)
 
    info = await get_device_summary(udid)
    if not info:
        typer.secho(f"Error: unable to fetch device info for {udid}.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
 
    typer.secho(
        "\nFor safety reasons, please confirm you want to erase this device.\n"
        "This action is irreversible.",
        fg=typer.colors.YELLOW,
    )
    typed = typer.prompt(f"Type the device UDID ({udid}) to confirm the erase")
    if typed != udid:
        typer.secho("UDID does not match. Erase operation cancelled.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
 
    device_label = info.get("nome") or udid
    typer.secho(
        f"\n⚠ WARNING: this will permanently erase all data on '{device_label}'. "
        "There is no way to undo this.",
        fg=typer.colors.RED,
        bold=True,
    )
    typer.confirm(f"Erase '{device_label}' now?", abort=True)
 
    last_percent = 0.0
 
    with typer.progressbar(length=100, label="Erasing device") as progress:
        def on_progress(percent: float) -> None:
            nonlocal last_percent
            delta = max(0.0, percent - last_percent)
            if delta:
                progress.update(delta)  # type: ignore
                last_percent = percent
 
        try:
            await erase_device(
                udid=udid,
                confirm_udid=typed,
                progress_callback=on_progress,
            )
        except PyMobileDevice3Exception as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
 
        ## Erase typically completes without granular progress events until the
        ## end; if progress has not reached 100%, complete the progress bar.
        if last_percent < 100:
            progress.update(100 - last_percent)  # type: ignore
 
    typer.secho("Device erased successfully.", fg=typer.colors.GREEN)
    
@app.command("restart")
@coro
async def restart(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help="Target iOS device UDID",
            prompt="Enter device UDID",
        ),
    ],
):
    """Restart the specified iOS device."""
    
    udid = await resolve_name(udid)

    await ensure_usbmuxd_or_exit()
 
    typer.secho(f"Restarting device {udid}...", bold=True)
    try:
        await restart_device(udid)
    except PyMobileDevice3Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
 
    typer.secho("Device restarted successfully.", fg=typer.colors.GREEN)

@app.command("shutdown")
@coro
async def shutdown(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help="Target iOS device UDID",
            prompt="Enter device UDID",
        ),
    ],
):
    """Shutdown the specified iOS device."""
    
    udid = await resolve_name(udid)

    await ensure_usbmuxd_or_exit()
 
    typer.secho(f"Shutting down device {udid}...", bold=True)
    try:
        await shutdown_device(udid)
    except PyMobileDevice3Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
 
    typer.secho("Device shut down successfully.", fg=typer.colors.GREEN)


@app.command("flash")
@coro
async def flash_firmware(
    udid: Annotated[
        Optional[str],
        typer.Option(
            "--udid",
            "-u",
            help="UDID of a normally-booted target device. Mutually exclusive with --ecid.",
        ),
    ] = None,
    ecid: Annotated[
        Optional[str],
        typer.Option(
            "--ecid",
            "-e",
            help="Hex ECID of a device already stuck in Recovery/DFU/WTF (see 'noot list-dfu'). Mutually exclusive with --udid.",
        ),
    ] = None,
    ipsw_file: Annotated[
        str,
        typer.Option(
            "--file", "-f",
            help="IPSW File Path or URL",
            prompt="Enter IPSW File Path...",
        ),
    ] = "",
    erase: Annotated[
        bool,
        typer.Option(
            "--erase/--no-erase",
            help="Erase and restore (factory reset) instead of updating in place.",
            prompt="Erase and restore? (factory reset, data loss)",
        ),
    ] = False,
):
    """Flash or restore the specified device from an IPSW (path or URL).
 
    Exactly one of --udid or --ecid must be given: --udid for a normally-
    booted device (the common case, equivalent to iTunes/Finder — the device
    reboots into Recovery mode on its own during the process); --ecid only
    if the device is already stuck in Recovery/DFU/WTF, e.g. after a failed
    update (get it from 'noot list-dfu').
    """
    if (udid is None) == (ecid is None):
        typer.secho("Error: specify exactly one of --udid or --ecid.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
 
    if not ipsw_file.startswith(("http://", "https://")) and not Path(ipsw_file).exists():
        typer.secho(f"Error: File {ipsw_file} does not exist", fg=typer.colors.RED)
        raise typer.Exit(code=1)
 
    ecid_int: Optional[int] = None
    if ecid is not None:
        try:
            ecid_int = int(ecid, 16)
        except ValueError:
            typer.secho(f"Error: '{ecid}' is not a valid hex ECID.", fg=typer.colors.RED)
            raise typer.Exit(code=1)
 
    await ensure_usbmuxd_or_exit()
 
    typer.secho("Checking target device...", bold=True)
    try:
        await validate_flash_target(udid, ecid_int)
    except DeviceNotFoundError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except RecoveryDeviceMismatchError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except IRecvError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        typer.secho(
            "Multiple devices in Recovery/DFU/WTF mode detected. "
            "Disconnect all but one and try again.",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=1)
    typer.secho("Target device confirmed.", fg=typer.colors.GREEN)
 
    typer.secho("Reading IPSW file information...", bold=True)
    try:
        ipsw = open_ipsw(ipsw_file)
        info = get_ipsw_file_info(ipsw)
    except Exception as e:
        typer.secho(f"Error reading IPSW file information: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
 
    ## Compatibility check only applies to the --udid path: a device already
    ## in Recovery/DFU/WTF cannot be queried via lockdown for its ProductType,
    ## so there is nothing to compare against ahead of time in that case.
    if udid is not None:
        summary = await get_device_summary(udid)
        product_type = summary.get("modello")
        typer.secho(f"Current device model: {product_type}", bold=True)
        if product_type not in info["supported_product_types"]:
            typer.secho(
                "Error: This IPSW file is not compatible with the connected device.",
                fg=typer.colors.RED,
                bold=True,
            )
            raise typer.Exit(code=1)
 
    typer.secho(
        "Summary: "
        f"iOS {info['product_version']} ({info['product_build_version']}) — "
        f"{'ERASE (factory reset)' if erase else 'UPDATE (preserve data)'}",
        bold=True,
    )
    typer.secho(
        "The device will reboot into Recovery mode and stay unusable until the process completes.",
        fg=typer.colors.YELLOW,
    )
    typer.secho(
        "Warning: back up your data first if you have not already — this cannot be undone.",
        fg=typer.colors.YELLOW,
        bold=True,
    )
    typer.confirm("Proceed with the flash?", abort=True)
 
    typer.secho("Flashing firmware...", bold=True)
    typer.secho(
        "This may take several minutes. Please keep the device connected and do not interrupt the process.",
        fg=typer.colors.YELLOW,
    )
    try:
        await flash_from_ipsw(udid=udid, ecid=ecid_int, ipsw=ipsw, erase=erase)
    except UnsupportedFirmwareFormatError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except PyMobileDevice3Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
 
    typer.secho("Flash completed.", fg=typer.colors.GREEN)
 
## @}



if __name__ == "__main__":
    try:
        app()
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        sys.exit(130)