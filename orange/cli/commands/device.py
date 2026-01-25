"""
Device-related CLI commands.

Commands for listing, inspecting, and pairing with iOS devices.
"""

from __future__ import annotations

import json
import sys
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from orange.core.connection import (
    ConnectionManager,
    DeviceDetector,
    DeviceInfo,
    PairingManager,
    DeviceState,
    ConnectionType,
)
from orange.exceptions import (
    DeviceNotFoundError,
    PairingError,
    PairingTimeoutError,
)


def get_console(ctx: click.Context) -> Console:
    """Get the Rich console from context."""
    return ctx.obj.get("console", Console())


def format_bytes(size: Optional[int]) -> str:
    """Format bytes as human-readable string."""
    if size is None:
        return "Unknown"

    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(size) < 1024:
            return f"{size:.1f} {unit}"
        size //= 1024
    return f"{size:.1f} PB"


def get_state_style(state: DeviceState) -> str:
    """Get Rich style for device state."""
    styles = {
        DeviceState.CONNECTED: "green",
        DeviceState.PAIRED: "green",
        DeviceState.UNPAIRED: "yellow",
        DeviceState.DISCONNECTED: "red",
        DeviceState.LOCKED: "yellow",
    }
    return styles.get(state, "white")


def get_battery_style(level: Optional[int]) -> str:
    """Get Rich style for battery level."""
    if level is None:
        return "white"
    if level <= 10:
        return "red bold"
    if level <= 20:
        return "yellow"
    return "green"


@click.group()
def device() -> None:
    """Manage iOS devices."""
    pass


@device.command("list")
@click.option(
    "--json", "as_json",
    is_flag=True,
    help="Output as JSON.",
)
@click.option(
    "--no-wifi",
    is_flag=True,
    help="Exclude Wi-Fi connected devices.",
)
@click.pass_context
def list_cmd(
    ctx: click.Context,
    as_json: bool,
    no_wifi: bool,
) -> None:
    """List connected iOS devices."""
    console = get_console(ctx)

    detector = DeviceDetector(include_wifi=not no_wifi)
    devices = detector.list_devices()

    if not devices:
        if as_json:
            click.echo("[]")
        else:
            console.print(
                "[yellow]No iOS devices found.[/yellow]\n"
                "Make sure your device is:\n"
                "  1. Connected via USB or Wi-Fi\n"
                "  2. Unlocked\n"
                "  3. Trusted (if prompted)"
            )
        return

    if as_json:
        output = [d.to_dict() for d in devices]
        click.echo(json.dumps(output, indent=2))
        return

    # Create table
    table = Table(title="Connected iOS Devices")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Model", style="magenta")
    table.add_column("iOS", style="green")
    table.add_column("UDID", style="dim")
    table.add_column("Connection", style="blue")
    table.add_column("Status")
    table.add_column("Battery")

    for dev in devices:
        # Format battery
        if dev.battery_level is not None:
            battery_text = f"{dev.battery_level}%"
            if dev.battery_charging:
                battery_text += " ⚡"
            battery = Text(battery_text, style=get_battery_style(dev.battery_level))
        else:
            battery = Text("-", style="dim")

        # Format status
        status = Text(
            dev.state.value.replace("_", " ").title(),
            style=get_state_style(dev.state)
        )

        # Format connection type
        conn_icon = "🔌" if dev.connection_type == ConnectionType.USB else "📶"
        conn_text = f"{conn_icon} {dev.connection_type.value.upper()}"

        table.add_row(
            dev.name,
            dev.model_number,
            dev.ios_version,
            dev.short_udid,
            conn_text,
            status,
            battery,
        )

    console.print(table)
    console.print(f"\n[dim]Found {len(devices)} device(s)[/dim]")


@device.command("info")
@click.argument("udid", required=False)
@click.option(
    "--json", "as_json",
    is_flag=True,
    help="Output as JSON.",
)
@click.option(
    "--all", "show_all",
    is_flag=True,
    help="Show all device information.",
)
@click.pass_context
def info_cmd(
    ctx: click.Context,
    udid: Optional[str],
    as_json: bool,
    show_all: bool,
) -> None:
    """Show detailed device information.

    If UDID is not specified and only one device is connected,
    that device will be used automatically.
    """
    console = get_console(ctx)

    detector = DeviceDetector()
    devices = detector.list_devices()

    if not devices:
        console.print("[red]No iOS devices found.[/red]")
        sys.exit(1)

    # If no UDID specified, use the first/only device
    if udid is None:
        if len(devices) > 1:
            console.print(
                "[yellow]Multiple devices found. Please specify UDID:[/yellow]"
            )
            for dev in devices:
                console.print(f"  {dev.udid}  ({dev.name})")
            sys.exit(1)
        device_info = devices[0]
    else:
        # Find device by UDID (support partial match)
        device_info = None
        for dev in devices:
            if dev.udid == udid or dev.udid.startswith(udid):
                device_info = dev
                break

        if device_info is None:
            console.print(f"[red]Device not found: {udid}[/red]")
            sys.exit(1)

    if as_json:
        output = device_info.to_dict()
        if show_all and device_info.extra:
            output["extra"] = device_info.extra
        click.echo(json.dumps(output, indent=2))
        return

    # Display device info
    title = f"📱 {device_info.name}"
    content = []

    # Basic info
    content.append(f"[bold]Model:[/bold] {device_info.model} ({device_info.model_number})")
    content.append(f"[bold]iOS Version:[/bold] {device_info.ios_version} ({device_info.build_version})")
    content.append(f"[bold]Serial Number:[/bold] {device_info.serial_number}")
    content.append(f"[bold]UDID:[/bold] {device_info.udid}")

    # Connection info
    conn_type = "USB" if device_info.connection_type == ConnectionType.USB else "Wi-Fi"
    content.append(f"[bold]Connection:[/bold] {conn_type}")

    if device_info.wifi_address:
        content.append(f"[bold]Wi-Fi Address:[/bold] {device_info.wifi_address}")

    # Status
    status_style = get_state_style(device_info.state)
    status_text = device_info.state.value.replace("_", " ").title()
    content.append(f"[bold]Status:[/bold] [{status_style}]{status_text}[/{status_style}]")

    # Battery
    if device_info.battery_level is not None:
        battery_style = get_battery_style(device_info.battery_level)
        charging = " (Charging)" if device_info.battery_charging else ""
        content.append(
            f"[bold]Battery:[/bold] [{battery_style}]{device_info.battery_level}%{charging}[/{battery_style}]"
        )

    # Storage
    if device_info.storage_total:
        total = format_bytes(device_info.storage_total)
        available = format_bytes(device_info.storage_available)
        content.append(f"[bold]Storage:[/bold] {available} available of {total}")

    # Extra info if requested
    if show_all and device_info.extra:
        content.append("")
        content.append("[bold underline]Additional Information[/bold underline]")
        for key, value in device_info.extra.items():
            if value is not None:
                formatted_key = key.replace("_", " ").title()
                content.append(f"[bold]{formatted_key}:[/bold] {value}")

    panel = Panel(
        "\n".join(content),
        title=title,
        border_style="cyan",
    )
    console.print(panel)


@device.command("pair")
@click.argument("udid", required=False)
@click.option(
    "--timeout", "-t",
    default=60,
    type=int,
    help="Timeout in seconds to wait for user acceptance.",
)
@click.pass_context
def pair_cmd(
    ctx: click.Context,
    udid: Optional[str],
    timeout: int,
) -> None:
    """Pair with an iOS device.

    If UDID is not specified and only one device is connected,
    that device will be used automatically.

    This will initiate the pairing process. You will need to:
    1. Unlock your device
    2. Tap "Trust" when prompted
    3. Enter your passcode (iOS 11+)
    """
    console = get_console(ctx)

    # Find device
    detector = DeviceDetector()
    devices = detector.list_devices()

    if not devices:
        console.print("[red]No iOS devices found.[/red]")
        console.print("Make sure your device is connected via USB and unlocked.")
        sys.exit(1)

    if udid is None:
        if len(devices) > 1:
            console.print("[yellow]Multiple devices found. Please specify UDID:[/yellow]")
            for dev in devices:
                console.print(f"  {dev.udid}  ({dev.name})")
            sys.exit(1)
        device_info = devices[0]
        udid = device_info.udid
    else:
        device_info = None
        for dev in devices:
            if dev.udid == udid or dev.udid.startswith(udid):
                device_info = dev
                udid = dev.udid  # Use full UDID
                break

        if device_info is None:
            console.print(f"[red]Device not found: {udid}[/red]")
            sys.exit(1)

    pairing_mgr = PairingManager(udid)

    # Check if already paired
    if pairing_mgr.is_paired():
        console.print(f"[green]Device '{device_info.name}' is already paired.[/green]")
        return

    console.print(f"Pairing with [cyan]{device_info.name}[/cyan]...")
    console.print()
    console.print("[yellow]Please unlock your device and tap 'Trust' when prompted.[/yellow]")
    console.print("[yellow]You may need to enter your passcode.[/yellow]")
    console.print()

    def on_prompt() -> None:
        console.print("[dim]Waiting for user to accept on device...[/dim]")

    try:
        with console.status("Pairing...") as status:
            success = pairing_mgr.pair(
                on_prompt=on_prompt,
                timeout=timeout,
            )

        if success:
            console.print(f"[green]✓ Successfully paired with '{device_info.name}'[/green]")
        else:
            console.print("[red]✗ Pairing failed[/red]")
            sys.exit(1)

    except PairingTimeoutError:
        console.print(
            f"[red]✗ Pairing timed out after {timeout} seconds.[/red]\n"
            "Please make sure to tap 'Trust' on your device."
        )
        sys.exit(1)

    except PairingError as e:
        console.print(f"[red]✗ Pairing error: {e}[/red]")
        sys.exit(1)


@device.command("unpair")
@click.argument("udid", required=False)
@click.option(
    "--yes", "-y",
    is_flag=True,
    help="Skip confirmation prompt.",
)
@click.pass_context
def unpair_cmd(
    ctx: click.Context,
    udid: Optional[str],
    yes: bool,
) -> None:
    """Remove pairing with an iOS device.

    If UDID is not specified and only one device is connected,
    that device will be used automatically.
    """
    console = get_console(ctx)

    # Find device
    detector = DeviceDetector()
    devices = detector.list_devices()

    if not devices:
        console.print("[red]No iOS devices found.[/red]")
        sys.exit(1)

    if udid is None:
        if len(devices) > 1:
            console.print("[yellow]Multiple devices found. Please specify UDID:[/yellow]")
            for dev in devices:
                console.print(f"  {dev.udid}  ({dev.name})")
            sys.exit(1)
        device_info = devices[0]
        udid = device_info.udid
    else:
        device_info = None
        for dev in devices:
            if dev.udid == udid or dev.udid.startswith(udid):
                device_info = dev
                udid = dev.udid
                break

        if device_info is None:
            console.print(f"[red]Device not found: {udid}[/red]")
            sys.exit(1)

    # Confirm
    if not yes:
        if not click.confirm(f"Unpair from '{device_info.name}'?"):
            console.print("Cancelled.")
            return

    pairing_mgr = PairingManager(udid)

    if pairing_mgr.unpair():
        console.print(f"[green]✓ Unpaired from '{device_info.name}'[/green]")
        console.print(
            "[dim]Note: To fully unpair, also go to Settings > General > "
            "Transfer or Reset > Reset Location & Privacy on your device.[/dim]"
        )
    else:
        console.print("[red]✗ Failed to unpair[/red]")
        sys.exit(1)


@device.command("is-paired")
@click.argument("udid", required=False)
@click.pass_context
def is_paired_cmd(ctx: click.Context, udid: Optional[str]) -> None:
    """Check if a device is paired.

    If UDID is not specified and only one device is connected,
    that device will be used automatically.
    """
    console = get_console(ctx)

    # Find device
    detector = DeviceDetector()
    devices = detector.list_devices()

    if not devices:
        console.print("[red]No iOS devices found.[/red]")
        sys.exit(1)

    if udid is None:
        if len(devices) > 1:
            console.print("[yellow]Multiple devices found. Please specify UDID:[/yellow]")
            for dev in devices:
                console.print(f"  {dev.udid}  ({dev.name})")
            sys.exit(1)
        found_udid = devices[0].udid
    else:
        found_udid = None
        for dev in devices:
            if dev.udid == udid or dev.udid.startswith(udid):
                found_udid = dev.udid
                break

        if found_udid is None:
            console.print(f"[red]Device not found: {udid}[/red]")
            sys.exit(1)

    pairing_mgr = PairingManager(found_udid)

    if pairing_mgr.is_paired():
        console.print("[green]Device is paired[/green]")
        sys.exit(0)
    else:
        console.print("[yellow]Device is not paired[/yellow]")
        sys.exit(1)


@device.command("ping")
@click.argument("udid", required=False)
@click.option(
    "--timeout", "-t",
    default=10,
    type=int,
    help="Connection timeout in seconds.",
)
@click.pass_context
def ping_cmd(
    ctx: click.Context,
    udid: Optional[str],
    timeout: int,
) -> None:
    """Test connection to a device.

    If UDID is not specified and only one device is connected,
    that device will be used automatically.
    """
    console = get_console(ctx)

    # Find device
    detector = DeviceDetector()
    devices = detector.list_devices()

    if not devices:
        console.print("[red]No iOS devices found.[/red]")
        sys.exit(1)

    if udid is None:
        if len(devices) > 1:
            console.print("[yellow]Multiple devices found. Please specify UDID:[/yellow]")
            for dev in devices:
                console.print(f"  {dev.udid}  ({dev.name})")
            sys.exit(1)
        device_info = devices[0]
        udid = device_info.udid
    else:
        device_info = None
        for dev in devices:
            if dev.udid == udid or dev.udid.startswith(udid):
                device_info = dev
                udid = dev.udid
                break

        if device_info is None:
            console.print(f"[red]Device not found: {udid}[/red]")
            sys.exit(1)

    manager = ConnectionManager()

    try:
        with console.status(f"Connecting to {device_info.name}..."):
            with manager.connect(udid, timeout=timeout) as conn:
                console.print(f"[green]✓ Connected to {conn.device_name}[/green]")
                console.print(f"  iOS {conn.ios_version}")
                console.print(f"  Model: {conn.model}")

    except DeviceNotFoundError:
        console.print(f"[red]✗ Device not found[/red]")
        sys.exit(1)

    except Exception as e:
        console.print(f"[red]✗ Connection failed: {e}[/red]")
        sys.exit(1)


@device.command("scan")
@click.option(
    "--timeout", "-t",
    default=10,
    type=int,
    help="Scan duration in seconds.",
)
@click.option(
    "--json", "as_json",
    is_flag=True,
    help="Output as JSON.",
)
@click.pass_context
def scan_cmd(
    ctx: click.Context,
    timeout: int,
    as_json: bool,
) -> None:
    """Scan for iOS devices on the network (Wi-Fi Sync).

    Discovers iOS devices using Bonjour/mDNS with Apple's standard
    Wi-Fi Sync protocol - the same used by iTunes and Finder.

    NO DEVELOPER MODE REQUIRED.

    Prerequisites:
    1. Device must be paired via USB first (one-time)
    2. Wi-Fi must be enabled: orange device wifi --enable
    3. Device and computer on the same network
    """
    console = get_console(ctx)

    try:
        from orange.core.connection.wireless import WirelessDiscovery

        discovery = WirelessDiscovery()

        with console.status(f"Scanning for Wi-Fi Sync devices ({timeout}s)..."):
            # Use discover_with_info to get UDID, model, iOS version
            devices = discovery.discover_with_info(timeout=float(timeout))

        if not devices:
            if as_json:
                click.echo("[]")
            else:
                console.print("[yellow]No wireless devices found.[/yellow]")
                console.print()
                console.print("To enable Wi-Fi access (one-time setup):")
                console.print("  1. Connect your device via USB")
                console.print("  2. Run: [bold]orange device pair[/bold]")
                console.print("  3. Run: [bold]orange device wifi --enable[/bold]")
                console.print("  4. Disconnect USB - device now accessible wirelessly")
                console.print()
                console.print("Make sure both devices are on the same Wi-Fi network.")
            return

        if as_json:
            output = [d.to_dict() for d in devices]
            click.echo(json.dumps(output, indent=2))
            return

        # Create table with more identifying columns
        table = Table(title="Wi-Fi Sync Devices")
        table.add_column("Device Name", style="cyan", no_wrap=True)
        table.add_column("Model", style="magenta")
        table.add_column("iOS", style="green")
        table.add_column("Address", style="blue")
        table.add_column("UDID", style="dim")

        for dev in devices:
            # Format UDID (shortened for display)
            udid_display = dev.udid[:8] + "..." if dev.udid else "-"

            table.add_row(
                dev.hostname or dev.name,
                dev.model or "-",
                dev.os_version or "-",
                f"{dev.address}:{dev.port}",
                udid_display,
            )

        console.print(table)
        console.print(f"\n[dim]Found {len(devices)} device(s)[/dim]")
        console.print("[dim]Use 'orange device list' to see full details.[/dim]")

    except ImportError as e:
        console.print(f"[red]Missing dependency: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Scan failed: {e}[/red]")
        sys.exit(1)


@device.command("wifi")
@click.option(
    "--enable/--disable",
    default=None,
    help="Enable or disable Wi-Fi connections.",
)
@click.option(
    "--status",
    is_flag=True,
    help="Show current Wi-Fi connection status.",
)
@click.argument("udid", required=False)
@click.pass_context
def wifi_cmd(
    ctx: click.Context,
    enable: Optional[bool],
    status: bool,
    udid: Optional[str],
) -> None:
    """Enable Wi-Fi Sync on a USB-connected device.

    This uses Apple's standard Wi-Fi Sync protocol (same as iTunes/Finder).
    NO DEVELOPER MODE REQUIRED.

    One-time setup (device must be connected via USB):

    \b
    1. Pair your device:
       $ orange device pair

    \b
    2. Enable Wi-Fi connections:
       $ orange device wifi --enable

    \b
    3. Disconnect USB - your device is now accessible wirelessly!
       $ orange device scan
       $ orange device list

    The device will be discoverable whenever it's on the same
    Wi-Fi network as your computer.
    """
    console = get_console(ctx)

    # Find device if UDID provided
    if udid:
        detector = DeviceDetector()
        device_info = None
        for dev in detector.list_devices():
            if dev.udid == udid or dev.udid.startswith(udid):
                udid = dev.udid
                device_info = dev
                break
        if device_info is None:
            console.print(f"[red]Device not found: {udid}[/red]")
            sys.exit(1)

    try:
        from orange.core.connection.wireless import (
            enable_wifi_connections,
            get_wifi_connections_state,
        )

        if status or enable is None:
            # Show status
            state = get_wifi_connections_state(udid)
            if state is None:
                console.print("[yellow]Could not determine Wi-Fi status.[/yellow]")
                console.print("Make sure a device is connected via USB.")
                sys.exit(1)
            elif state:
                console.print("[green]Wi-Fi connections: ENABLED[/green]")
                console.print()
                console.print("Your device is accessible wirelessly when on the same network.")
                console.print("Run [bold]orange device scan[/bold] to find it.")
            else:
                console.print("[yellow]Wi-Fi connections: DISABLED[/yellow]")
                console.print()
                console.print("To enable, run: [bold]orange device wifi --enable[/bold]")
            return

        # Enable or disable
        if enable:
            console.print("Enabling Wi-Fi connections...")
            success = enable_wifi_connections(udid, enable=True)
            if success:
                console.print("[green]✓ Wi-Fi connections enabled![/green]")
                console.print()
                console.print("You can now disconnect USB and access your device wirelessly:")
                console.print("  1. Disconnect the USB cable")
                console.print("  2. Run: [bold]orange device scan[/bold]")
                console.print("  3. Run: [bold]orange device list[/bold]")
            else:
                console.print("[red]✗ Failed to enable Wi-Fi connections[/red]")
                sys.exit(1)
        else:
            console.print("Disabling Wi-Fi connections...")
            success = enable_wifi_connections(udid, enable=False)
            if success:
                console.print("[green]✓ Wi-Fi connections disabled[/green]")
            else:
                console.print("[red]✗ Failed to disable Wi-Fi connections[/red]")
                sys.exit(1)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print()
        console.print("Make sure your device is connected via USB and paired.")
        sys.exit(1)
