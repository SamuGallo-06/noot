import asyncio
from functools import wraps
from pathlib import Path
import sys
from typing import Annotated

from platformdirs import user_data_dir
import typer

from idevice import (
    check_usbmuxd,
    get_connected_devices,
    get_device_summary,
    usbmuxd_socket_exists,
)
# Import the interactive wizard from our separate module
from tui import run_interactive_wizard

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


async def ensure_usbmuxd_running(gui: bool = False):
    """Check if usbmuxd is running. If absent or unresponsive, attempt to restart it."""
    auth_tool = "pkexec" if gui else "sudo"

    async def run_sys_cmd(cmd: list[str]) -> bool:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0

    if not usbmuxd_socket_exists():
        typer.secho(
            f"[WARNING] usbmuxd socket missing. Attempting to start via {auth_tool}...",
            fg=typer.colors.YELLOW,
        )
        await run_sys_cmd([auth_tool, "systemctl", "start", "usbmuxd"])

    if not await check_usbmuxd():
        typer.secho(
            "[WARNING] usbmuxd is unresponsive. Attempting restart...",
            fg=typer.colors.YELLOW,
        )
        await run_sys_cmd([auth_tool, "systemctl", "restart", "usbmuxd"])


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


###################################
##          Commands             ##
###################################

@app.command("list")
@coro
async def list_devices():
    """List all connected iOS devices."""
    await ensure_usbmuxd_running()

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
        typer.echo(f"  • {name} ({udid})")


@app.command("summary")
@coro
async def summary(
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
    """Display detailed hardware and system info for a specific device."""
    await ensure_usbmuxd_running()

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
):
    """Run a local backup for the specified device."""
    await ensure_usbmuxd_running()

    backup_dir.mkdir(parents=True, exist_ok=True)

    typer.echo(f"Starting backup for device: {udid}")
    typer.echo(f"Destination: {backup_dir}")

    # TODO: Implement actual backup execution
    typer.secho("Backup operation not yet implemented.", fg=typer.colors.YELLOW)


if __name__ == "__main__":
    try:
        app()
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        sys.exit(130)