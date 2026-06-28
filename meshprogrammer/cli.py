"""Command-line interface for backing up and restoring Meshtastic device configs."""

import argparse
import getpass
import sys
import threading
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from meshtastic.mesh_interface import MeshInterface
from werkzeug.serving import make_server

from meshprogrammer import backup as backup_module
from meshprogrammer import connection, crypto, device, meshtastic_web, storage
from meshprogrammer.web import create_app


def _add_working_dir_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--working-dir",
        type=Path,
        default=storage.DEFAULT_WORKING_DIR,
        help="Folder to store/read device config backups (default: %(default)s)",
    )


def _add_connection_args(parser: argparse.ArgumentParser) -> None:
    """Add the mutually exclusive --port (serial) / --ble args for picking a device."""
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--port",
        default=None,
        help="Serial port the device is connected on, e.g. COM3 "
        "(auto-detected if exactly one Meshtastic device is connected)",
    )
    group.add_argument(
        "--ble",
        nargs="?",
        const="any",
        default=None,
        help="Connect over BLE instead of serial, optionally naming the device "
        "(defaults to the only nearby Meshtastic BLE device, if there's exactly one)",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the meshprogrammer argument parser.

    ``--working-dir`` is defined per-subcommand (rather than on the top-level
    parser) so it works the same way whether typed before or after the
    subcommand name -- the latter is required for the mesh-* script shortcuts,
    which always prepend the subcommand themselves.
    """
    parser = argparse.ArgumentParser(
        prog="meshprogrammer",
        description="Backup and restore Meshtastic device configs",
        epilog=(
            "backup, restore, device-backups, export-channels, and import-channels accept "
            "--port (auto-detected if exactly one device is connected) or --ble to connect "
            "over Bluetooth instead. backup and export-channels also accept --encrypt to "
            "password-protect the saved file. Run 'meshprogrammer <command> --help' for a "
            "command's full options."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("help", help="List all commands")

    scan_parser = subparsers.add_parser("scan", help="List connected Meshtastic serial devices")
    scan_parser.add_argument(
        "--ble",
        action="store_true",
        help="Scan for nearby Meshtastic BLE devices instead of serial ports",
    )

    backup_parser = subparsers.add_parser("backup", help="Back up a connected device's config")
    _add_working_dir_arg(backup_parser)
    _add_connection_args(backup_parser)
    backup_parser.add_argument(
        "--encrypt",
        action="store_true",
        help="Prompt for a password and encrypt the backup file",
    )

    restore_parser = subparsers.add_parser("restore", help="Restore a backup onto a connected device")
    _add_working_dir_arg(restore_parser)
    _add_connection_args(restore_parser)
    restore_target = restore_parser.add_mutually_exclusive_group()
    restore_target.add_argument(
        "--file", type=Path, default=None, help="Specific backup file to restore"
    )
    restore_target.add_argument(
        "--node-id",
        default=None,
        help="Restore the latest backup for this node id, instead of the connected device's own",
    )

    list_parser = subparsers.add_parser("list", help="List known devices and their backups")
    _add_working_dir_arg(list_parser)

    device_backups_parser = subparsers.add_parser(
        "device-backups",
        help="List backups for the connected device (auto-detected if only one)",
    )
    _add_working_dir_arg(device_backups_parser)
    _add_connection_args(device_backups_parser)

    list_channels_parser = subparsers.add_parser(
        "list-channels", help="List known channel sets saved with export-channels"
    )
    _add_working_dir_arg(list_channels_parser)

    export_channels_parser = subparsers.add_parser(
        "export-channels", help="Save a connected device's channels to a named, sharable file"
    )
    _add_working_dir_arg(export_channels_parser)
    _add_connection_args(export_channels_parser)
    export_channels_parser.add_argument(
        "--encrypt",
        action="store_true",
        help="Prompt for a password and encrypt the saved channel set",
    )
    export_channels_parser.add_argument("name", help="Name to save the channel set as")

    import_channels_parser = subparsers.add_parser(
        "import-channels",
        help="Apply a saved channel set to a connected device, overwriting its current channels",
    )
    _add_working_dir_arg(import_channels_parser)
    _add_connection_args(import_channels_parser)
    import_channels_parser.add_argument("name", help="Name of the saved channel set to apply")

    gui_parser = subparsers.add_parser("gui", help="Start the local web GUI in your browser")
    _add_working_dir_arg(gui_parser)
    gui_parser.add_argument(
        "--http-port",
        type=int,
        default=None,
        help="Port for the local web server (default: an OS-assigned free port)",
    )

    meshtastic_web_parser = subparsers.add_parser(
        "meshtastic-web",
        help="Download (if needed) and open the official Meshtastic web client locally",
    )
    _add_working_dir_arg(meshtastic_web_parser)
    meshtastic_web_parser.add_argument(
        "--http-port",
        type=int,
        default=meshtastic_web.DEFAULT_PORT,
        help="Port for the local web server (default: %(default)s)",
    )
    meshtastic_web_parser.add_argument(
        "--client-version",
        default=meshtastic_web.DEFAULT_VERSION,
        help="meshtastic/web release tag to download and serve (default: %(default)s)",
    )

    return parser


def run_help() -> int:
    """Print the full list of commands and usage (same as --help)."""
    build_parser().print_help()
    return 0


def run_scan(ble: bool) -> int:
    """List connected Meshtastic devices: serial ports, or nearby BLE devices if ``ble``."""
    if ble:
        devices = device.scan_ble()
        if not devices:
            print("No Meshtastic BLE devices detected.")
            return 0
        for ble_device in devices:
            print(ble_device)
        return 0
    ports = device.scan_ports()
    if not ports:
        print("No Meshtastic devices detected.")
        return 0
    for port in ports:
        print(port)
    return 0


def _prompt_new_password() -> str:
    """Prompt for a new password, retrying until two entries match and it's non-empty."""
    while True:
        password = getpass.getpass("Encryption password: ")
        if not password:
            print("Password cannot be empty.")
            continue
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords did not match, try again.")
            continue
        return password


def _prompt_existing_password() -> str:
    return getpass.getpass("Password: ")


def _resolve_port(port: str | None) -> str | None:
    """Return ``port`` unchanged, or auto-detect it if not given explicitly.

    Auto-detection only succeeds when exactly one Meshtastic device is
    connected. Returns None (after printing an error) if there's none or
    more than one and the caller didn't say which to use.
    """
    try:
        return connection.resolve_port(port)
    except connection.PortResolutionError as exc:
        suffix = " Specify --port." if not exc.ports else " Specify --port to choose one."
        print(str(exc) + suffix)
        return None


def _connection_label(port: str | None, ble: str | None) -> str:
    return f"BLE ({ble})" if ble is not None else str(port)


def _decrypt_if_needed(data: dict[str, Any]) -> dict[str, Any] | None:
    """Return ``data`` as-is if it's a plain payload, or prompt and decrypt if encrypted.

    Returns None (after printing an error) if the password was wrong.
    """
    if not crypto.is_encrypted(data):
        return data
    password = _prompt_existing_password()
    try:
        return crypto.decrypt_payload(data, password)
    except crypto.WrongPasswordError:
        print("Incorrect password.")
        return None


def run_backup(working_dir: Path, port: str | None, ble: str | None, encrypt: bool) -> int:
    """Back up the config of the device on ``port``/``ble`` (port auto-detected if neither given)."""
    if ble is None:
        port = _resolve_port(port)
        if port is None:
            return 1
    with device.open_device(port, ble) as interface:
        payload = device.backup_from_interface(interface)
    node_id = payload["node_id"]
    if encrypt:
        payload = crypto.encrypt_payload(payload, _prompt_new_password())
    timestamp = datetime.now(timezone.utc)
    path = storage.write_backup(working_dir, node_id, payload, timestamp)
    print(f"Backed up {node_id} to {path}" + (" (encrypted)" if encrypt else ""))
    return 0


def _apply_restore(interface: MeshInterface, backup_path: Path) -> bool:
    """Decrypt (if needed) and restore the backup at ``backup_path``.

    Returns False (after printing an error) if an encrypted backup's
    password was wrong.
    """
    data = _decrypt_if_needed(storage.read_backup(backup_path))
    if data is None:
        return False
    parsed = backup_module.parse_backup_payload(data)
    device.restore_to_interface(interface, parsed)
    print(f"Restored {backup_path} to device")
    return True


def run_restore(
    working_dir: Path, port: str | None, ble: str | None, file: Path | None, node_id: str | None
) -> int:
    """Restore a backup onto the device on ``port``/``ble`` (port auto-detected if neither given).

    If ``file`` is given, restore that exact backup. Otherwise restore the
    latest backup for ``node_id``, or for the connected device's own node id
    if ``node_id`` is also not given.
    """
    if ble is None:
        port = _resolve_port(port)
        if port is None:
            return 1

    if file is not None:
        with device.open_device(port, ble) as interface:
            if not _apply_restore(interface, file):
                return 1
        return 0

    with device.open_device(port, ble) as interface:
        target_node_id = node_id or device.get_node_id(interface)
        backup_path = storage.latest_backup(working_dir, target_node_id)
        if backup_path is None:
            print(f"No backups found for {target_node_id} in {working_dir}")
            return 1
        if not _apply_restore(interface, backup_path):
            return 1
    return 0


def _print_backup_list(node_id: str, backups: list[Path]) -> None:
    suffix = "" if len(backups) == 1 else "s"
    print(f"{node_id} ({len(backups)} backup{suffix})")
    for backup_file in backups:
        print(f"  {backup_file.name}")


def run_list(working_dir: Path) -> int:
    """Print known devices and their backups."""
    device_ids = storage.list_device_ids(working_dir)
    if not device_ids:
        print(f"No backups found in {working_dir}")
        return 0
    for node_id in device_ids:
        _print_backup_list(node_id, storage.list_backups(working_dir, node_id))
    return 0


def run_device_backups(working_dir: Path, port: str | None, ble: str | None) -> int:
    """Print backups for the device on ``port``/``ble`` (port auto-detected if neither given)."""
    if ble is None:
        port = _resolve_port(port)
        if port is None:
            return 1
    with device.open_device(port, ble) as interface:
        node_id = device.get_node_id(interface)
    backups = storage.list_backups(working_dir, node_id)
    if not backups:
        print(f"No backups found for {node_id} in {working_dir}")
        return 0
    _print_backup_list(node_id, backups)
    return 0


def run_list_channels(working_dir: Path) -> int:
    """Print known channel set names, marking which ones are encrypted."""
    names = storage.list_channel_names(working_dir)
    if not names:
        print(f"No channel sets found in {working_dir / 'channels'}")
        return 0
    for name in names:
        suffix = " (encrypted)" if crypto.is_encrypted(storage.read_channels(working_dir, name)) else ""
        print(f"{name}{suffix}")
    return 0


def run_export_channels(
    working_dir: Path, port: str | None, ble: str | None, name: str, encrypt: bool
) -> int:
    """Save the connected device's channels to a named, sharable file.

    ``port`` is auto-detected if neither it nor ``ble`` is given.
    """
    if ble is None:
        port = _resolve_port(port)
        if port is None:
            return 1
    with device.open_device(port, ble) as interface:
        channel_url = device.export_channel_url(interface)
    payload: dict[str, Any] = {"channel_url": channel_url}
    if encrypt:
        payload = crypto.encrypt_payload(payload, _prompt_new_password())
    path = storage.write_channels(working_dir, name, payload)
    print(f"Saved channels as '{name}' to {path}" + (" (encrypted)" if encrypt else ""))
    return 0


def run_import_channels(working_dir: Path, port: str | None, ble: str | None, name: str) -> int:
    """Apply a saved channel set to the connected device, overwriting its current channels.

    ``port`` is auto-detected if neither it nor ``ble`` is given.
    """
    try:
        data = storage.read_channels(working_dir, name)
    except FileNotFoundError:
        print(f"No saved channel set named '{name}' in {working_dir}")
        return 1

    data = _decrypt_if_needed(data)
    if data is None:
        return 1

    if ble is None:
        port = _resolve_port(port)
        if port is None:
            return 1

    with device.open_device(port, ble) as interface:
        device.import_channel_url(interface, data["channel_url"])
    print(f"Applied channel set '{name}' to device on {_connection_label(port, ble)}")
    return 0


def _start_meshtastic_web_alongside_gui(working_dir: Path) -> Any:
    """Best-effort start of the meshtastic-web client server on its default port.

    Returns the running server (already serving in a background thread),
    or None if it couldn't be started -- e.g. no network for a first-time
    download, or the port's already taken by a separately-running
    ``mesh-meshtastic-web``. Either way, ``gui`` keeps working without it.
    """
    try:
        client_dir = meshtastic_web.ensure_client_downloaded(working_dir)
    except RuntimeError as exc:
        print(f"Meshtastic web client: couldn't download it, continuing without it ({exc})")
        return None
    try:
        server = make_server(
            "127.0.0.1", meshtastic_web.DEFAULT_PORT, meshtastic_web.create_static_app(client_dir)
        )
    except OSError as exc:
        print(
            f"Meshtastic web client: port {meshtastic_web.DEFAULT_PORT} unavailable, "
            f"assuming it's already running separately ({exc})"
        )
        return None
    print(f"Meshtastic web client running at http://127.0.0.1:{server.server_port}/")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def run_gui(working_dir: Path, http_port: int | None, open_browser: bool = True) -> int:
    """Start the local web GUI and open it in the default browser.

    Binds to 127.0.0.1 only -- this serves real hardware control and
    filesystem actions, never reachable from the LAN. If ``http_port``
    isn't given, the OS assigns a free ephemeral port. ``make_server``
    binds and starts listening before returning, so opening the browser
    right after is safe -- no guessed delay needed.

    Also starts the meshtastic-web client server alongside (best-effort,
    on its fixed default port -- matching the link already shown in the
    GUI), and stops it when this does.
    """
    app = create_app(working_dir)
    server = make_server("127.0.0.1", http_port or 0, app)
    url = f"http://127.0.0.1:{server.server_port}/"

    meshtastic_web_server = _start_meshtastic_web_alongside_gui(working_dir)

    print(f"meshprogrammer GUI running at {url} (Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if meshtastic_web_server is not None:
            meshtastic_web_server.shutdown()
    return 0


def run_meshtastic_web(
    working_dir: Path, http_port: int, version: str, open_browser: bool = True
) -> int:
    """Download (if needed), serve, and open the official Meshtastic web client.

    Binds to 127.0.0.1 only, same as ``gui``. The release is cached under
    ``working_dir/.meshtastic-web-client/<version>/`` so later runs skip
    the download. Defaults to a fixed port (unlike ``gui``'s ephemeral
    one) so the web GUI's link to it stays valid across runs.
    """
    client_dir = meshtastic_web.ensure_client_downloaded(working_dir, version)
    app = meshtastic_web.create_static_app(client_dir)
    server = make_server("127.0.0.1", http_port, app)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Meshtastic web client running at {url} (Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "help":
        return run_help()
    if args.command == "scan":
        return run_scan(args.ble)
    if args.command == "backup":
        return run_backup(args.working_dir, args.port, args.ble, args.encrypt)
    if args.command == "restore":
        return run_restore(args.working_dir, args.port, args.ble, args.file, args.node_id)
    if args.command == "list":
        return run_list(args.working_dir)
    if args.command == "device-backups":
        return run_device_backups(args.working_dir, args.port, args.ble)
    if args.command == "list-channels":
        return run_list_channels(args.working_dir)
    if args.command == "export-channels":
        return run_export_channels(args.working_dir, args.port, args.ble, args.name, args.encrypt)
    if args.command == "import-channels":
        return run_import_channels(args.working_dir, args.port, args.ble, args.name)
    if args.command == "gui":
        return run_gui(args.working_dir, args.http_port)
    if args.command == "meshtastic-web":
        return run_meshtastic_web(args.working_dir, args.http_port, args.client_version)

    parser.error(f"Unknown command: {args.command}")
    return 1


def _run_subcommand(subcommand: str, argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    return main([subcommand, *argv])


def help_entry_point(argv: list[str] | None = None) -> int:
    """Console-script shortcut for ``meshprogrammer help``."""
    return _run_subcommand("help", argv)


def scan_entry_point(argv: list[str] | None = None) -> int:
    """Console-script shortcut for ``meshprogrammer scan``."""
    return _run_subcommand("scan", argv)


def backup_entry_point(argv: list[str] | None = None) -> int:
    """Console-script shortcut for ``meshprogrammer backup``."""
    return _run_subcommand("backup", argv)


def restore_entry_point(argv: list[str] | None = None) -> int:
    """Console-script shortcut for ``meshprogrammer restore``."""
    return _run_subcommand("restore", argv)


def list_entry_point(argv: list[str] | None = None) -> int:
    """Console-script shortcut for ``meshprogrammer list``."""
    return _run_subcommand("list", argv)


def device_backups_entry_point(argv: list[str] | None = None) -> int:
    """Console-script shortcut for ``meshprogrammer device-backups``."""
    return _run_subcommand("device-backups", argv)


def list_channels_entry_point(argv: list[str] | None = None) -> int:
    """Console-script shortcut for ``meshprogrammer list-channels``."""
    return _run_subcommand("list-channels", argv)


def export_channels_entry_point(argv: list[str] | None = None) -> int:
    """Console-script shortcut for ``meshprogrammer export-channels``."""
    return _run_subcommand("export-channels", argv)


def import_channels_entry_point(argv: list[str] | None = None) -> int:
    """Console-script shortcut for ``meshprogrammer import-channels``."""
    return _run_subcommand("import-channels", argv)


def gui_entry_point(argv: list[str] | None = None) -> int:
    """Console-script shortcut for ``meshprogrammer gui``."""
    return _run_subcommand("gui", argv)


def meshtastic_web_entry_point(argv: list[str] | None = None) -> int:
    """Console-script shortcut for ``meshprogrammer meshtastic-web``."""
    return _run_subcommand("meshtastic-web", argv)


if __name__ == "__main__":
    sys.exit(main())
