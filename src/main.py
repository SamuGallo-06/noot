import asyncio
from functools import wraps
from pathlib import Path
import shutil
import sys
from typing import Annotated, Optional
 
import typer
import click
import settings

from rich.console import Console
from rich.table import Table 
 
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import Qt,QLocale, QTranslator

from i18n import tr, ngettext, LOCALE_DIR
 
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
    get_ipsw_file_info,
    flash_from_ipsw,
    validate_flash_target,
    RecoveryDeviceMismatchError,
    exit_recovery_mode, 
    NotInRecoveryModeError,
    IRecvNoDeviceConnectedError
)

from idevicerestore_bridge import IdevicerestoreNotInstalledError, IdevicerestoreError
from settings import get_backup_directory
 
# Importing UI
from gui.main_window import MainWindow

VERSION="1.0.0"

MAX_PASSWORD_ATTEMPTS = 3

app = typer.Typer(
    help=tr("NOOT - iOS device management and backup utility"),
    no_args_is_help=True,
)

console = Console()

_active_translators: list[QTranslator] = []

def coro(f):
    """Decorator to run async functions inside synchronous Typer commands."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

def version_callback():
    typer.echo(tr("NOOT version: {version}").format(version=VERSION))
    raise typer.Exit()

def apply_language(app: QApplication, lang_code: str) -> None:
    global _active_translators

    for translator in _active_translators:
        app.removeTranslator(translator)
    _active_translators = []

    if lang_code == "en":
        return

    translator = QTranslator(app)
    qm_path = Path(__file__).parent / "assets" / "locales" / f"noot_{lang_code}.qm"
    if translator.load(str(qm_path)):
        app.installTranslator(translator)
        _active_translators.append(translator)
    else:
        print(tr("Unable to load translations for '{lang_code}'").format(lang_code=lang_code))


def apply_theme(theme: str) -> None:
    hints = QGuiApplication.styleHints()
    if theme == "light":
        hints.setColorScheme(Qt.ColorScheme.Light)
    elif theme == "dark":
        hints.setColorScheme(Qt.ColorScheme.Dark)
    else:  # system
        hints.setColorScheme(Qt.ColorScheme.Unknown)


def launch_gui():
    """Launch the graphical user interface."""
    app = QApplication(sys.argv)
    app.setApplicationName("Noot")

    cfg = settings.load()
    apply_language(app, cfg.get("ui", "language"))
    apply_theme(cfg.get("ui", "theme"))

    window = MainWindow()
    window.setWindowTitle("Noot - iOS Device Management Utility")
    window.show()
    sys.exit(app.exec())

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    gui: Annotated[
        bool,
        typer.Option("--gui", "-g", help=tr("Launch GUI interface")),
    ] = False,
    version: Annotated[
        bool,
        typer.Option("--version", "-v", help=tr("Display the current version"))
    ] = False,
):
    """Global entry point: intercepts --gui or triggers interactive mode when no command is provided."""
    if gui:
        typer.echo(tr("Launching graphical user interface..."))
        launch_gui()
        raise typer.Exit()
    
    if version:
        version_callback()

    # Fallback to interactive mode if no CLI arguments/commands are supplied
    if ctx.invoked_subcommand is None:
        typer.echo(tr("No command provided. use --help for usage information."))
        raise typer.Exit()


## Helper function to resolve device name or UDID to a valid UDID, with error handling and user feedback.
async def resolve_name(name_or_udid: str) -> str:
    try:
        udid = await resolve_device_identifier(name_or_udid)
    except DeviceNotFoundError as e:
        typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except AmbiguousDeviceNameError as e:
            typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
            raise typer.Exit(code=1)
    return udid

async def ensure_usbmuxd_or_exit(gui: bool = False):
    """@brief Wrap ensure_usbmuxd_running and map its status to CLI output and exit codes."""
    status = await ensure_usbmuxd_running(gui=gui)
    if status == UsbmuxdStatus.STARTED:
        typer.secho(tr("usbmuxd was not running and has been started."), fg=typer.colors.GREEN)
    elif status == UsbmuxdStatus.FAILED:
        typer.secho(
            tr("Error: usbmuxd is unreachable and could not be started automatically.\n") +
            tr("Try manually: sudo systemctl start usbmuxd"),
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    
async def probe_boot_state_or_none():
    """Try to detect a device in DFU/Recovery/WTF mode without raising exceptions."""
    try:
        return await get_boot_state_device(), False
    except IRecvError:
        return None, True

## @name Commands
## @{

@app.command("list", help=tr("List all connected iOS devices (normal mode and DFU/Recovery/WTF)."))
@coro
async def list_devices():
    """List all connected iOS devices (normal mode and DFU/Recovery/WTF)."""
    status = await ensure_usbmuxd_running()
    if status == UsbmuxdStatus.FAILED:
        typer.secho(tr("Error: usbmuxd is unreachable."), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    elif status == UsbmuxdStatus.STARTED:
        typer.secho(tr("usbmuxd was restarted successfully."), fg=typer.colors.GREEN)

    if not await check_usbmuxd():
        typer.secho(tr("Error: usbmuxd is unreachable."), fg=typer.colors.RED)
        raise typer.Exit(code=1)

    devices = await get_connected_devices()
    boot_device, multiple_boot_devices = await probe_boot_state_or_none()

    if not devices and boot_device is None and not multiple_boot_devices:
        typer.echo(tr("No devices detected."))
        return

    if devices:
        typer.secho((tr("Connected devices:")), bold=True)
        table = Table()
        table.add_column(tr("Name"), style="cyan")
        table.add_column("UDID", style="magenta")
        for d in devices:
            name = d.get("name", tr("Unknown"))
            udid = d.get("udid")
            table.add_row(name, udid)
        console.print(table)

    if multiple_boot_devices:
        typer.secho(
            tr("Multiple devices in DFU/Recovery/WTF mode detected.\n") + tr("Disconnect all but one to see its details."),
            fg=typer.colors.YELLOW,
        )
    elif boot_device is not None:
        typer.secho(tr("Devices in DFU/Recovery/WTF mode:"), bold=True, fg=typer.colors.YELLOW)
        table = Table()
        table.add_column(tr("Mode"), style="yellow")
        table.add_column(tr("Model"), style="cyan")
        table.add_column(tr("ECID"), style="magenta")
        table.add_row(
            boot_device["state"].name.replace("_", " ").title(),
            boot_device.get("display_name") or tr("Unknown"),
            f"{boot_device['ecid']:x}",
        )
        console.print(table)
        typer.echo(tr("Use 'noot list-dfu' for more details."))

@app.command(
    "list-dfu",
    help=tr(
        "Check for a device in DFU, Recovery, or WTF mode (single instant check).\n\n"
        "Unlike 'list', this does not go through usbmuxd: devices in these modes "
        "are invisible to it. Useful before a firmware flash, or while waiting for "
        "a device to enter DFU (re-run the command until it shows up)."
    ),
)
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
        typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
        typer.secho(
            tr("Multiple devices in DFU/Recovery/WTF mode detected. "
               "Disconnect all but one and try again."),
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=1)

    if device is None:
        typer.echo(tr("No device in DFU/Recovery/WTF mode detected."))
        return

    label = device["state"].name.replace("_", " ").title()
    typer.secho(tr("Device in {label} mode:").format(label=label), bold=True, fg=typer.colors.YELLOW)
    table = Table(show_header=False)
    table.add_row(tr("Model"), device.get("display_name") or tr("Unknown"))
    table.add_row(tr("ECID"), f"{device['ecid']:x}")
    table.add_row(tr("Serial"), device.get("serial") or tr("Unknown"))
    table.add_row(tr("iBoot version"), device.get("iboot_version") or tr("Unknown"))
    console.print(table)

@app.command("summary", help=tr("Display detailed hardware and system info for a specific device."))
@coro
async def summary(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help=tr("Device UDID or name (e.g. 'iPhone 5c'). Use 'noot list' to see options."),
            prompt=tr("Enter device UDID or name"),
        ),
    ],
):
    """Display detailed hardware and system info for a specific device."""
    udid = await resolve_name(udid)
    
    status = await ensure_usbmuxd_running()
    if status == UsbmuxdStatus.FAILED:
        typer.secho(tr("Error: usbmuxd is unreachable."), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    elif status == UsbmuxdStatus.STARTED:
        typer.secho(tr("usbmuxd was restarted successfully."), fg=typer.colors.GREEN)

    info = await get_device_summary(udid)
    if not info:
        typer.secho(
            tr("Error: Unable to fetch summary for device {udid}").format(udid=udid),
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    typer.secho(tr("Device Summary [{udid}]:").format(udid=udid), bold=True)
    for k, v in info.items():
        typer.echo(f"  {k}: {v}")

@app.command(
    "enable-encryption",
    help=tr(
        "Enable backup encryption on the device by setting a new backup password.\n\n"
        "NOOT always performs encrypted backups, so this must be run once before the "
        "first backup (unless encryption is already enabled on the device, e.g. via "
        "a previous iTunes/Finder pairing)."
    ),
)
@coro
async def enable_encryption(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help=tr("Device UDID or name. Use 'noot list' to see options."),
            prompt=tr("Enter device UDID or name"),
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
        typer.secho(tr("Backup encryption is already enabled on this device."), fg=typer.colors.GREEN)
        return
 
    typer.secho(
        tr("This password protects your backups. Passsword must be at least 8 characters long and contain both letters and numbers and special characters. Store it safely: it cannot be recovered, and you will need it to restore or read this device's backups."),
        fg=typer.colors.YELLOW,
    )
    
    typer.confirm(tr("Do you want to enable encryption?"))
    
    password = typer.prompt(
        text=tr("Choose a password"),
        default=None,
        hide_input=True,       
        confirmation_prompt=True,
        type=str,                
    )
    
    ## Handle password errors.
    if(password is None):
        typer.secho(tr("Error: Password cannot be empty."), fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if(password.strip() == ""):
        typer.secho(tr("Error: Password cannot be empty or whitespace."), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    if len(password) < 4:
        typer.secho(tr("Error: Password must be at least 4 characters long."), fg=typer.colors.RED)
        raise typer.Exit(code=1)

    """if(not any(char.isdigit() for char in password) or
       not any(char.isalpha() for char in password) or
       not any(not char.isalnum() for char in password)):
        typer.secho(tr("Error: Password must contain both letters and numbers and special characters."), fg=typer.colors.RED)
        raise typer.Exit(code=1)"""
    
    ## Enable backup encryption.
    
    await enable_backup_encryption(udid, password)
    typer.secho(tr("Backup encryption enabled successfully."), fg=typer.colors.GREEN)


@app.command("change-encryption-password", help=tr("Change the current backup encryption password on the device."))
@coro
async def change_encryption_password(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help=tr("Device UDID or name. Use 'noot list' to see options."),
            prompt=tr("Enter device UDID or name"),
        ),
    ],
):
    """Change the current backup encryption password on the device."""
    udid = await resolve_name(udid)
    await ensure_usbmuxd_or_exit()

    if not await is_backup_encrypted(udid):
        typer.secho(tr("Error: backup encryption is not enabled on this device."), fg=typer.colors.RED)
        raise typer.Exit(code=1)

    old_password = typer.prompt(tr("Current backup password"), hide_input=True)
    new_password = typer.prompt(
        tr("New backup password"),
        hide_input=True,
        confirmation_prompt=True,
    )
    if not new_password.strip():
        typer.secho(tr("Error: Password cannot be empty or whitespace."), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if len(new_password) < 4:
        typer.secho(tr("Error: Password must be at least 4 characters long."), fg=typer.colors.RED)
        raise typer.Exit(code=1)

    try:
        await change_backup_encryption_password(udid, old_password, new_password)
    except IncorrectBackupPasswordError as e:
        typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho(tr("Backup encryption password changed successfully."), fg=typer.colors.GREEN)
  
@app.command("disable-encryption", help=tr("Disable backup encryption on the device (requires the current backup password)."))
@coro
async def disable_encryption(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help=tr("Device UDID or name. Use 'noot list' to see options."),
            prompt=tr("Enter device UDID or name"),
        ),
    ],
):
    """Disable backup encryption on the device (requires the current backup password)."""
    udid = await resolve_name(udid)
    await ensure_usbmuxd_or_exit()
 
    if not await is_backup_encrypted(udid):
        typer.secho(tr("Backup encryption is already disabled on this device."), fg=typer.colors.GREEN)
        return
 
    for attempt in range(1, MAX_PASSWORD_ATTEMPTS + 1):
        password = typer.prompt(tr("Current backup password"), hide_input=True)
        try:
            await disable_backup_encryption(udid, password)
        except IncorrectBackupPasswordError:
            remaining = MAX_PASSWORD_ATTEMPTS - attempt
            if remaining > 0:
                typer.secho(
                    ngettext(
                        "Incorrect password. {remaining} attempt remaining.",
                        "Incorrect password. {remaining} attempts remaining.",
                        remaining,
                    ).format(remaining=remaining),
                    fg=typer.colors.RED,
                )
                continue
            typer.secho(tr("Error: too many incorrect attempts."), fg=typer.colors.RED)
            raise typer.Exit(code=1)
        else:
            typer.secho(tr("Backup encryption disabled."), fg=typer.colors.GREEN)
            return
        
@app.command("list-backups", help=tr("List local backups available in the backup folder."))
@coro
async def list_backups(
    backup_dir: Annotated[
        Path,
        typer.Option(
            "--backup-dir",
            "-d",
            help=tr("Folder containing local backups"),
        ),
    ] = get_backup_directory(),
):
    """List local backups available in the backup folder."""
    backups = list_local_backups(backup_dir)
    if not backups:
        typer.echo(tr("No backups found in {dir}.").format(dir=backup_dir))
        return
 
    typer.secho(
        ngettext(
            "{count} backup found in {dir}:",
            "{count} backups found in {dir}:",
            len(backups),
        ).format(count=len(backups), dir=backup_dir),
        bold=True,
    )
        
    table = Table()

    ## Define the table columns (style, alignment, and width).
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column(tr("Device Name"))
    table.add_column("UDID", justify="center")
    table.add_column(tr("Date"), justify="right")

    for i, b in enumerate(backups):  
        name = b["device_name"] or tr("Unknown device")
        date = b["backup_date"] or tr("Unknown date")
        udid = b['udid']
        table.add_row(str(i), str(name), str(udid), str(date))

    console.print(table)

@app.command("backup", help=tr("Run a local backup for the specified device."))
@coro
async def backup(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help=tr("Device UDID or name. Use 'noot list' to see options."),
            prompt=tr("Enter device UDID or name"),
        ),
    ],
    backup_dir: Annotated[
        Path,
        typer.Option(
            "--backup-dir",
            "-d",
            help=tr("Destination folder for backup files"),
        ),
    ] = get_backup_directory(),
    full_backup: Annotated[
        bool,
        typer.Option(
            "--full-backup",
            "-fb",
            help=tr("Perform Full Backup")
        ),
    ] = False,
    exclude: Annotated[
        Optional[list[str]],
        typer.Option(
            "--exclude",
            "-e",
            click_type=click.Choice(list(EXCLUDABLE_CATEGORIES.keys())),  # pyright: ignore[reportArgumentType]
            help=tr("Category to exclude from the backup. Repeatable."),
        ),
    ] = None,
    ):
    """Run a local backup for the specified device."""
    
    udid = await resolve_name(udid)
    
    status = await ensure_usbmuxd_running()
    if status == UsbmuxdStatus.FAILED:
        typer.secho(tr("Error: usbmuxd is unreachable."), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    elif status == UsbmuxdStatus.STARTED:
        typer.secho(tr("usbmuxd was restarted successfully."), fg=typer.colors.GREEN)
        
    backup_dir.mkdir(parents=True, exist_ok=True)

    if not await is_backup_encrypted(udid):
        typer.secho(
            tr("Error: backup encryption is not enabled on this device.\n"
               "Run 'noot enable-encryption --udid ...' first."),
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    typer.secho(
        tr("This backup will be encrypted. Please enter "
           "recovered, and you'll need it to restore or read this backup later."),
        fg=typer.colors.YELLOW,
    )
    password = typer.prompt(tr("Backup password"), hide_input=True)
    
    typer.secho(tr("Starting full backup") if full_backup else tr("Starting incremental backup"), bold=True)
    typer.echo(tr("Device: {udid}").format(udid=udid))
    typer.echo(tr("Destination: {dir}").format(dir=backup_dir))
    if exclude:
        typer.echo(tr("Excluding: {categories}").format(categories=", ".join(exclude)))
    typer.echo(tr("Keep the device connected and unlocked until the backup finishes.\n"))
    
    last_percent = 0.0
 
    with typer.progressbar(length=100, label=tr("Backing up")) as progress:
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
            typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
            raise typer.Exit(code=1)
        except IncrementalExcludeConflictError as e:
            typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
            raise typer.Exit(code=1)
        except IncorrectBackupPasswordError as e:
            typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
            raise typer.Exit(code=1)
 
    typer.secho(tr("Backup completed successfully."), fg=typer.colors.GREEN)

@app.command("restore", help=tr("Restore a local backup onto the connected device."))
@coro
async def restore(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help=tr("Target iOS device UDID (the device connected now, that will receive the restore)."),
            prompt=tr("Enter device UDID"),
        ),
    ],
    source_udid: Annotated[
        Optional[str],
        typer.Option(
            "--source-udid",
            "-s",
            help=(
                tr("UDID of the backup to restore, if different from the target device. "
                   "Defaults to the target device's own UDID (restore its own latest backup). "
                   "Use 'noot list-backups' to see what's available.")
            ),
        ),
    ] = None,
    backup_dir: Annotated[
        Path,
        typer.Option(
            "--backup-dir",
            "-d",
            help=tr("Folder containing local backups"),
        ),
    ] = get_backup_directory(),
    remove_items_not_in_backup: Annotated[
        bool,
        typer.Option(
            "--remove-extra-data/--keep-extra-data",
            help=(
                tr("Remove data on the device that isn't present in the backup "
                   "(mirror restore). Default: keep extra data untouched.")
            ),
        ),
    ] = False,
):
    """Restore a local backup onto the connected device."""
    
    udid = await resolve_name(udid)
    
    status = await ensure_usbmuxd_running()
    if status == UsbmuxdStatus.FAILED:
        typer.secho(tr("Error: usbmuxd is unreachable."), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    elif status == UsbmuxdStatus.STARTED:
        typer.secho(tr("usbmuxd was restarted successfully."), fg=typer.colors.GREEN)
 
    ## If omitted, the source is the target device by default.
    source = source_udid or udid
 
    typer.secho(tr("Restore backup"), bold=True)
    typer.echo(tr("Target device: {udid}").format(udid=udid))
    if source != udid:
        typer.secho(
            tr("⚠ You are restoring a backup from a DIFFERENT device ({source}) "
               "onto this one ({udid}).").format(source=source, udid=udid),
            fg=typer.colors.YELLOW,
        )
    else:
        typer.echo(tr("Backup source: {source} (same as target)").format(source=source))
    typer.echo(tr("Backup location: {dir}").format(dir=backup_dir))
 
    warning_lines = [
        tr("\nRestoring will overwrite existing data on the target device with the "
           "contents of this backup. This cannot be undone."),
    ]
    if remove_items_not_in_backup:
        warning_lines.append(
            tr("⚠ --remove-extra-data is enabled: any data on the device NOT present "
               "in this backup will also be deleted.")
        )
    typer.secho("\n".join(warning_lines), fg=typer.colors.YELLOW)
    typer.confirm(tr("Do you want to continue?"), abort=True)
    
    typer.secho(
        tr("The device will restart automatically once the restore is complete. "
           "Keep it connected until then."),
        fg = typer.colors.BLUE
    )
 
    ## Check that the backup exists before requesting the password, so the user
    ## does not enter a password unnecessarily after specifying a wrong UDID.
    if not (backup_dir / source).exists():
        available = list_local_backups(backup_dir)
        typer.secho(tr("Error: no backup found for '{source}' in {dir}.").format(source=source, dir=backup_dir), fg=typer.colors.RED)
        if available:
            typer.echo(tr("Available backups:"))
            for b in available:
                name = b["device_name"] or tr("Unknown device")
                typer.echo(f"  • {name} (UDID: {b['udid']})")
        raise typer.Exit(code=1)

    password = typer.prompt(tr("Backup password (leave blank if not encrypted): "), hide_input=True)
 
    typer.secho(
        tr("\nFor safety reasons, please confirm you want to restore this device from a backup."),
        fg=typer.colors.RED,
        bold=True,
    )
    typed = typer.prompt(tr("Type the device UDID ({udid}) to confirm the restore").format(udid=udid))
    if typed != udid:
        typer.secho(tr("UDID does not match. Restore cancelled."), fg=typer.colors.RED)
        raise typer.Exit(code=1)
 
    last_percent = 0.0
 
    with typer.progressbar(length=100, label=tr("Restoring backup")) as progress:
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
            typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
            raise typer.Exit(code=1)
        except RestorePasswordRequiredError as e:
            typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
            raise typer.Exit(code=1)
        except IncorrectBackupPasswordError as e:
            typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
            raise typer.Exit(code=1)
 
    typer.secho(tr("Backup restored successfully."), fg=typer.colors.GREEN)

@app.command("delete", help=tr("Delete a local backup for the specified device UDID."))
@coro
async def delete(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help=tr("Target iOS device UDID"),
            prompt=tr("Enter device UDID"),
        ),
    ],
    backup_dir: Annotated[
        Path,
        typer.Option(
            "--backup-dir",
            "-d",
            help=tr("Destination folder for backup files"),
        ),
    ] = get_backup_directory(), 
):
    """Delete a local backup for the specified device UDID."""
    
    udid = await resolve_name(udid)

    backups = list_local_backups(backup_dir)
    backup_to_delete = next((b for b in backups if b["udid"] == udid), None)
    if not backup_to_delete:
        typer.secho(tr("No backup found for UDID {udid} in {dir}.").format(udid=udid, dir=backup_dir), fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho(
        tr("Are you sure you want to delete the backup for device '{name}' (UDID: {udid})?").format(name=backup_to_delete["device_name"], udid=udid),
        fg=typer.colors.YELLOW,
    )
    typer.confirm(tr("This action cannot be undone. Continue?"), abort=True)

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
            typer.secho(tr("Backup for UDID {udid} deleted successfully.").format(udid=udid), fg=typer.colors.GREEN)
        else:
            typer.secho(tr("Backup directory {path} does not exist.").format(path=backup_path), fg=typer.colors.RED)
            raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(tr("Error deleting backup: {error}").format(error=e), fg=typer.colors.RED)
        raise typer.Exit(code=1)



@app.command("erase", help=tr("Erase all data on the specified iOS device, restoring it to factory settings."))
@coro
async def erase(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help=tr("Target iOS device UDID"),
            prompt=tr("Enter device UDID"),
        ),
    ],
):
    """Erase all data on the specified iOS device, restoring it to factory settings."""
    
    udid = await resolve_name(udid)
    
    await ensure_usbmuxd_or_exit()
 
    typer.secho(
        tr("This operation will completely erase all data, settings, apps and "
           "personal files on the device, restoring it to its factory settings.\n"),
        fg=typer.colors.YELLOW,
        bold=True,
    )
    typer.echo(
        tr("Before continuing, on the device:\n"
           "  1. Make sure the battery is charged at least 50%.\n"
           "  2. Turn off Find My (Settings > [Your Name] > Find My > Find My iPhone/iPad, "
           "and turn it off).\n"
           "  3. Keep the device connected via USB and do not disconnect it during the process.\n")
    )
    typer.confirm(tr("Have you completed the steps above and want to continue?"), abort=True)
 
    info = await get_device_summary(udid)
    if not info:
        typer.secho(tr("Error: unable to fetch device info for {udid}.").format(udid=udid), fg=typer.colors.RED)
        raise typer.Exit(code=1)
 
    typer.secho(
        tr("\nFor safety reasons, please confirm you want to erase this device.\n"
           "This action is irreversible."),
        fg=typer.colors.YELLOW,
    )
    typed = typer.prompt(tr("Type the device UDID ({udid}) to confirm the erase").format(udid=udid))
    if typed != udid:
        typer.secho(tr("UDID does not match. Erase operation cancelled."), fg=typer.colors.RED)
        raise typer.Exit(code=1)
 
    device_label = info.get("nome") or udid
    typer.secho(
        tr("\n⚠ WARNING: this will permanently erase all data on '{device_label}'. "
           "There is no way to undo this.").format(device_label=device_label),
        fg=typer.colors.RED,
        bold=True,
    )
    typer.confirm(tr("Erase '{device_label}' now?").format(device_label=device_label), abort=True)
 
    last_percent = 0.0
 
    with typer.progressbar(length=100, label=tr("Erasing device")) as progress:
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
            typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
            raise typer.Exit(code=1)
 
        ## Erase typically completes without granular progress events until the
        ## end; if progress has not reached 100%, complete the progress bar.
        if last_percent < 100:
            progress.update(100 - last_percent)  # type: ignore
 
    typer.secho(tr("Device erased successfully."), fg=typer.colors.GREEN)
    
@app.command("restart", help=tr("Restart the specified iOS device."))
@coro
async def restart(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help=tr("Target iOS device UDID"),
            prompt=tr("Enter device UDID"),
        ),
    ],
):
    """Restart the specified iOS device."""
    
    udid = await resolve_name(udid)

    await ensure_usbmuxd_or_exit()
 
    typer.secho(tr("Restarting device {udid}...").format(udid=udid), bold=True)
    try:
        await restart_device(udid)
    except PyMobileDevice3Exception as e:
        typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
        raise typer.Exit(code=1)
 
    typer.secho(tr("Device restarted successfully."), fg=typer.colors.GREEN)

@app.command("shutdown", help=tr("Shutdown the specified iOS device."))
@coro
async def shutdown(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help=tr("Target iOS device UDID"),
            prompt=tr("Enter device UDID"),
        ),
    ],
):
    """Shutdown the specified iOS device."""
    
    udid = await resolve_name(udid)

    await ensure_usbmuxd_or_exit()
 
    typer.secho(tr("Shutting down device {udid}...").format(udid=udid), bold=True)
    try:
        await shutdown_device(udid)
    except PyMobileDevice3Exception as e:
        typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
        raise typer.Exit(code=1)
 
    typer.secho(tr("Device shut down successfully."), fg=typer.colors.GREEN)


@app.command(
    "flash",
    help=tr(
        "Flash or restore the specified device from an IPSW (path or URL).\n\n"
        "Exactly one of --udid or --ecid must be given: --udid for a normally-booted "
        "device (the common case, equivalent to iTunes/Finder — the device reboots "
        "into Recovery mode on its own during the process); --ecid only if the device "
        "is already stuck in Recovery/DFU/WTF, e.g. after a failed update "
        "(get it from 'noot list-dfu')."
    ),
)
@coro
async def flash_firmware(
    udid: Annotated[
        Optional[str],
        typer.Option(
            "--udid",
            "-u",
            help=tr("UDID of a normally-booted target device. Mutually exclusive with --ecid."),
        ),
    ] = None,
    ecid: Annotated[
        Optional[str],
        typer.Option(
            "--ecid",
            "-e",
            help=tr("Hex ECID of a device already stuck in Recovery/DFU/WTF (see 'noot list-dfu'). Mutually exclusive with --udid."),
        ),
    ] = None,
    ipsw_file: Annotated[
        str,
        typer.Option(
            "--file", "-f",
            help=tr("IPSW File Path or URL"),
            prompt=tr("Enter IPSW File Path..."),
        ),
    ] = "",
    erase: Annotated[
        bool,
        typer.Option(
            "--erase/--no-erase",
            help=tr("Erase and restore (factory reset) instead of updating in place."),
            prompt=tr("Erase and restore? (factory reset, data loss)"),
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
        typer.secho(tr("Error: specify exactly one of --udid or --ecid."), fg=typer.colors.RED)
        raise typer.Exit(code=1)
 
    if not ipsw_file.startswith(("http://", "https://")) and not Path(ipsw_file).exists():
        typer.secho(tr("Error: File {file} does not exist").format(file=ipsw_file), fg=typer.colors.RED)
        raise typer.Exit(code=1)
 
    ecid_int: Optional[int] = None
    if ecid is not None:
        try:
            ecid_int = int(ecid, 16)
        except ValueError:
            typer.secho(tr("Error: '{ecid}' is not a valid hex ECID.").format(ecid=ecid), fg=typer.colors.RED)
            raise typer.Exit(code=1)
 
    await ensure_usbmuxd_or_exit()
 
    typer.secho(tr("Checking target device..."), bold=True)
    try:
        await validate_flash_target(udid, ecid_int)
    except DeviceNotFoundError as e:
        typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except RecoveryDeviceMismatchError as e:
        typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    except IRecvError as e:
        typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
        typer.secho(
            tr("Multiple devices in Recovery/DFU/WTF mode detected. "
               "Disconnect all but one and try again."),
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=1)
    typer.secho(tr("Target device confirmed."), fg=typer.colors.GREEN)
 
    typer.secho(tr("Reading IPSW file information..."), bold=True)
    try:
        info = get_ipsw_file_info(ipsw_file)
    except Exception as e:
        typer.secho(tr("Error reading IPSW file information: {error}").format(error=e), fg=typer.colors.RED)
        raise typer.Exit(code=1)
 
    ## Compatibility check only applies to the --udid path: a device already
    ## in Recovery/DFU/WTF cannot be queried via lockdown for its ProductType,
    ## so there is nothing to compare against ahead of time in that case.
    if udid is not None:
        summary = await get_device_summary(udid)
        product_type = summary.get("modello")
        typer.secho(tr("Current device model: {model}").format(model=product_type), bold=True)
        if product_type not in info["supported_product_types"]:
            typer.secho(
                tr("Error: This IPSW file is not compatible with the connected device."),
                fg=typer.colors.RED,
                bold=True,
            )
            raise typer.Exit(code=1)
 
    typer.secho(
        tr("Summary: iOS {version} ({build}) — {mode}").format(
            version=info["product_version"],
            build=info["product_build_version"],
            mode=tr("ERASE (factory reset)") if erase else tr("UPDATE (preserve data)"),
        ),
        bold=True,
    )
    typer.secho(
        tr("The device will reboot into Recovery mode and stay unusable until the process completes."),
        fg=typer.colors.YELLOW,
    )
    typer.secho(
        tr("Warning: back up your data first if you have not already — this cannot be undone."),
        fg=typer.colors.YELLOW,
        bold=True,
    )
    typer.confirm(tr("Proceed with the flash?"), abort=True)
 
    typer.secho(tr("Flashing firmware..."), bold=True)
    typer.secho(
        tr("This may take several minutes. Please keep the device connected and do not interrupt the process."),
        fg=typer.colors.YELLOW,
    )
    
    def _show_step(step_label: Optional[str]) -> str:
        return step_label or ""
    
    last_percent = 0.0
    current_step_label = ""
    
    with typer.progressbar(
        length=100,
        label=tr("Flashing firmware..."),
        item_show_func=_show_step,
    ) as progressbar:
        def _on_progress(progress) -> None:
            nonlocal last_percent, current_step_label
            current_step_label = progress.step_label
            delta = max(0.0, progress.overall_progress - last_percent)
            if delta:
                progressbar.update(int(delta))
            last_percent = progress.overall_progress

        try:
            await flash_from_ipsw(
                udid=udid,
                ecid=ecid_int,
                ipsw_path=ipsw_file,
                erase=erase,
                progress_callback=_on_progress,
            )
        except IdevicerestoreNotInstalledError as e:
            typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
            raise typer.Exit(code=1)
        except IdevicerestoreError as e:
            typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
            raise typer.Exit(code=1)

        remaining = 100.0 - last_percent
        if remaining > 0:
            progressbar.update(int(remaining))

    typer.secho(tr("Flash completed."), fg=typer.colors.GREEN)
    
@app.command(
    "exit-recovery",
    help=tr(
        "Reboot a device out of Recovery mode into a normal boot.\n\n"
        "Works only in Recovery mode: DFU and WTF have no command interpreter, so "
        "a device in those states must be rebooted using the physical buttons."
    ),
)
@coro
async def exit_recovery(
    ecid: Annotated[
        str,
        typer.Option(
            "--ecid",
            "-e",
            help=tr("Hex ECID of the device in Recovery mode (see 'noot list-dfu')."),
            prompt=tr("Enter device ECID"),
        ),
    ],
):
    """Reboot a device out of Recovery mode into a normal boot.

    Works only in Recovery mode: DFU and WTF have no command interpreter, so
    a device in those states must be rebooted using the physical buttons.
    """
    try:
        ecid_int = int(ecid, 16)
    except ValueError:
        typer.secho(tr("Error: '{ecid}' is not a valid hex ECID.").format(ecid=ecid), fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho(
        tr("The device will reboot normally. This does NOT flash or erase anything. "
           "If the installed system is damaged, the device will return to Recovery on its own "
           "and will need 'noot flash'."),
        fg=typer.colors.YELLOW,
    )
    typer.confirm(tr("Reboot the device out of Recovery mode?"), abort=True)

    try:
        await exit_recovery_mode(ecid_int)
    except NotInRecoveryModeError as e:
        typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
        typer.secho(
            tr("To leave DFU/WTF mode, hold the power and home/volume buttons "
               "until the device restarts."),
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=1)
    except IRecvNoDeviceConnectedError:
        typer.secho(
            tr("Error: no device in Recovery/DFU/WTF mode found with ECID {ecid:x}.").format(ecid=ecid_int),
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    except IRecvError as e:
        typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
        typer.secho(
            tr("Multiple devices in Recovery/DFU/WTF mode detected. "
               "Disconnect all but one and try again."),
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=1)

    typer.secho(
        tr("Reboot command sent. The device should reappear in 'noot list' within a few seconds."),
        fg=typer.colors.GREEN,
    )
    
config_app = typer.Typer(help=tr("View and edit Noot configuration."))
app.add_typer(config_app, name="config")

@config_app.command("show", help=tr("Show the whole configuration."))
def config_show():
    """Show the whole configuration."""
    cfg = settings.load()
    for section in cfg.sections():
        typer.secho(f"[{section}]", bold=True)
        for key, value in cfg.items(section):
            typer.echo(f"{key} = {value}")

@config_app.command("get", help=tr("Print the value of a single key."))
def config_get(
    key: Annotated[
        str, 
        typer.Argument(help=tr("Key as section.key, e.g. backup.dir"))
    ],
):
    """Print the value of a single key."""
    section, _, name = key.partition(".")
    cfg = settings.load()
    if not cfg.has_option(section, name):
        typer.secho(tr("Error: unknown key '{key}'.").format(key=key), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.echo(cfg.get(section, name))

@config_app.command("set", help=tr("Set a key to a new value."))
def config_set(
    key: Annotated[
        str, 
        typer.Argument(help=tr("Key as section.key"))
    ],
    value: Annotated[
        str, 
        typer.Argument(help=tr("New value"))
    ],
):
    """Set a key to a new value."""
    section, _, name = key.partition(".")
    cfg = settings.load()
    if not cfg.has_section(section):
        typer.secho(tr("Error: unknown section '{section}'.").format(section=section), fg=typer.colors.RED)
        raise typer.Exit(code=1)
    cfg.set(section, name, value)
    settings.save(cfg)
    typer.secho(f"{key} = {value}", fg=typer.colors.GREEN)
    
@config_app.command("export", help=tr("Export the Noot configuration to a file."))
def config_export(
    output_path: Annotated[
        str,
        typer.Argument(help=tr("Path to the exported configuration file. The Noot configuration will be written to this file."))
    ]
):
    try:
        shutil.copy2(settings.CONFIG_PATH, output_path)
    except Exception as e:
        typer.secho(tr("Error: {error}").format(error=e), fg=typer.colors.RED)
    else:
        typer.secho(tr("Configuration exported successfully."))

@config_app.command("load", help=tr("Load a configuration file into Noot."))
def config_load(
    input_path: Annotated[
        str,
        typer.Argument(help=tr("Path to the configuration file to load into Noot."))
    ]
):
    result, cfg = settings.validate(Path(input_path))
    if(result != "SUCCESS"):
        typer.secho(tr("Invalid configuration file."))
        typer.secho(result, fg=typer.colors.RED)
    else:
        ## A None check is not necessary because a None configuration is returned when the result message is not SUCCESS, which is handled above.
        settings.save(cfg) #type: ignore
        typer.secho(tr("Configuration loaded successfully"), fg=typer.colors.GREEN)
        
@config_app.command("check", help=tr("Check that the current configuration file is valid."))
def config_check():
    result, _ = settings.validate(settings.CONFIG_PATH)
    if(result != "SUCCESS"):
        typer.secho(tr("Invalid configuration file."))
        typer.secho(result, fg=typer.colors.RED)
    else:
        typer.secho(tr("Valid configuration file"), fg=typer.colors.GREEN)
        
        
    
            
            
    
 
## @}

if __name__ == "__main__":
    try:
        app()
    except KeyboardInterrupt:
        print(tr("\nProcess interrupted by user."))
        sys.exit(130)