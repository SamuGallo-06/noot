import asyncio
from functools import wraps
from pathlib import Path
import sys
from typing import Annotated, Optional
 
from platformdirs import user_data_dir
import typer
import click
 
from idevice import (
    check_usbmuxd,
    get_connected_devices,
    get_device_summary,
    ensure_usbmuxd_running,
    UsbmuxdStatus,
    is_backup_encrypted,
    enable_backup_encryption,
    disable_backup_encryption,
    run_backup,
    EncryptionNotEnabledError,
    IncrementalExcludeConflictError,
    EXCLUDABLE_CATEGORIES,
    IncorrectBackupPasswordError,
)

MAX_PASSWORD_ATTEMPTS = 3

DEFAULT_BACKUP_DIR = Path(user_data_dir("noot", "SamuGallo-06")) / "backups"

app = typer.Typer(
    help="NOOT - iOS device management and backup utility",
    no_args_is_help=False,
)

def coro(f):
    """Decorator to run async functions inside synchronous Typer commands."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    gui: Annotated[
        bool,
        typer.Option("--gui", help="Launch GUI interface"),
    ] = False,
):
    """Global entry point: intercepts --gui or triggers interactive mode when no command is provided."""
    if gui:
        typer.echo("Launching graphical user interface...")
        # TODO: Initialize and launch GUI
        raise typer.Exit()

    # Fallback to interactive mode if no CLI arguments/commands are supplied
    if ctx.invoked_subcommand is None:
        typer.echo("No command provided. use --help for usage information.")
        raise typer.Exit()
    
async def ensure_usbmuxd_or_exit(gui: bool = False):
    """Wrapper CLI attorno a ensure_usbmuxd_running: traduce lo stato in output/exit code."""
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



###################################
##          Commands             ##
###################################

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
    for d in devices:
        name = d.get("name", "Unknown")
        udid = d.get("udid")
        typer.echo(f"  > {name} (UDID: {udid})")


@app.command("summary")
@coro
async def summary(
    udid: Annotated[
        str,
        typer.Option(
            "--udid",
            "-u",
            help="Target iOS device UDID. It can be obtained using the 'list' command.",
            prompt="Enter device UDID",
        ),
    ],
):
    """Display detailed hardware and system info for a specific device."""
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
            help="Target iOS device UDID. It can be obtained using the 'list' command.",
            prompt="Enter device UDID",
        ),
    ],
):
    
    """Enable backup encryption on the device by setting a new backup password.
 
    NOOT always performs encrypted backups, so this must be run once before the
    first backup (unless encryption is already enabled on the device, e.g. via
    a previous iTunes/Finder pairing).
    """

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
    
    ## Password Error Handle
    if(password is None):
        typer.secho("Error: Password cannot be empty.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if(password.strip() == ""):
        typer.secho("Error: Password cannot be empty or whitespace.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    if len(password) < 8:
        typer.secho("Error: Password must be at least 8 characters long.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if(not any(char.isdigit() for char in password) or
       not any(char.isalpha() for char in password) or
       not any(not char.isalnum() for char in password)):
        typer.secho("Error: Password must contain both letters and numbers and special characters.", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    
    ## Enable Encryption
    
    await enable_backup_encryption(udid, password)
    typer.secho("Backup encryption enabled successfully.", fg=typer.colors.GREEN)

    
@app.command("disable-encryption")
@coro
async def disable_encryption(
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
    """Disable backup encryption on the device (requires the current backup password)."""
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


@app.command("backup")
@coro
async def backup(
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
 
    typer.secho("Backup completed successfully.", fg=typer.colors.GREEN)

@app.command("restore")
@coro
def restore(
    
):
    pass

if __name__ == "__main__":
    try:
        app()
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        sys.exit(130)