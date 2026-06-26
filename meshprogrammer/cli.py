"""Command-line interface for backing up and restoring Meshtastic device configs."""

import argparse
import getpass
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from meshtastic.serial_interface import SerialInterface

from meshprogrammer import backup as backup_module
from meshprogrammer import crypto, device, storage


def _add_working_dir_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--working-dir",
        type=Path,
        default=storage.DEFAULT_WORKING_DIR,
        help="Folder to store/read device config backups (default: %(default)s)",
    )


def _add_port_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--port",
        default=None,
        help="Serial port the device is connected on, e.g. COM3 "
        "(auto-detected if exactly one Meshtastic device is connected)",
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
            "--port (auto-detected if exactly one device is connected). backup and "
            "export-channels also accept --encrypt to password-protect the saved file. "
            "Run 'meshprogrammer <command> --help' for a command's full options."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("help", help="List all commands")

    subparsers.add_parser("scan", help="List connected Meshtastic serial devices")

    backup_parser = subparsers.add_parser("backup", help="Back up a connected device's config")
    _add_working_dir_arg(backup_parser)
    _add_port_arg(backup_parser)
    backup_parser.add_argument(
        "--encrypt",
        action="store_true",
        help="Prompt for a password and encrypt the backup file",
    )

    restore_parser = subparsers.add_parser("restore", help="Restore a backup onto a connected device")
    _add_working_dir_arg(restore_parser)
    _add_port_arg(restore_parser)
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
    _add_port_arg(device_backups_parser)

    export_channels_parser = subparsers.add_parser(
        "export-channels", help="Save a connected device's channels to a named, sharable file"
    )
    _add_working_dir_arg(export_channels_parser)
    _add_port_arg(export_channels_parser)
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
    _add_port_arg(import_channels_parser)
    import_channels_parser.add_argument("name", help="Name of the saved channel set to apply")

    return parser


def run_help() -> int:
    """Print the full list of commands and usage (same as --help)."""
    build_parser().print_help()
    return 0


def run_scan() -> int:
    """List connected Meshtastic serial devices."""
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
    if port is not None:
        return port
    ports = device.scan_ports()
    if len(ports) == 1:
        return ports[0]
    if not ports:
        print("No Meshtastic devices detected. Specify --port.")
        return None
    print(f"Multiple devices detected ({', '.join(ports)}). Specify --port to choose one.")
    return None


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


def run_backup(working_dir: Path, port: str | None, encrypt: bool) -> int:
    """Back up the config of the device connected on ``port`` (auto-detected if not given)."""
    port = _resolve_port(port)
    if port is None:
        return 1
    with device.open_device(port) as interface:
        payload = device.backup_from_interface(interface)
    node_id = payload["node_id"]
    if encrypt:
        payload = crypto.encrypt_payload(payload, _prompt_new_password())
    timestamp = datetime.now(timezone.utc)
    path = storage.write_backup(working_dir, node_id, payload, timestamp)
    print(f"Backed up {node_id} to {path}" + (" (encrypted)" if encrypt else ""))
    return 0


def _apply_restore(interface: SerialInterface, backup_path: Path) -> bool:
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


def run_restore(working_dir: Path, port: str | None, file: Path | None, node_id: str | None) -> int:
    """Restore a backup onto the device connected on ``port`` (auto-detected if not given).

    If ``file`` is given, restore that exact backup. Otherwise restore the
    latest backup for ``node_id``, or for the connected device's own node id
    if ``node_id`` is also not given.
    """
    port = _resolve_port(port)
    if port is None:
        return 1

    if file is not None:
        with device.open_device(port) as interface:
            if not _apply_restore(interface, file):
                return 1
        return 0

    with device.open_device(port) as interface:
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


def run_device_backups(working_dir: Path, port: str | None) -> int:
    """Print backups for the connected device (auto-detected if not given)."""
    port = _resolve_port(port)
    if port is None:
        return 1
    with device.open_device(port) as interface:
        node_id = device.get_node_id(interface)
    backups = storage.list_backups(working_dir, node_id)
    if not backups:
        print(f"No backups found for {node_id} in {working_dir}")
        return 0
    _print_backup_list(node_id, backups)
    return 0


def run_export_channels(working_dir: Path, port: str | None, name: str, encrypt: bool) -> int:
    """Save the connected device's channels to a named, sharable file.

    ``port`` is auto-detected if not given and exactly one device is connected.
    """
    port = _resolve_port(port)
    if port is None:
        return 1
    with device.open_device(port) as interface:
        channel_url = device.export_channel_url(interface)
    payload: dict[str, Any] = {"channel_url": channel_url}
    if encrypt:
        payload = crypto.encrypt_payload(payload, _prompt_new_password())
    path = storage.write_channels(working_dir, name, payload)
    print(f"Saved channels as '{name}' to {path}" + (" (encrypted)" if encrypt else ""))
    return 0


def run_import_channels(working_dir: Path, port: str | None, name: str) -> int:
    """Apply a saved channel set to the connected device, overwriting its current channels.

    ``port`` is auto-detected if not given and exactly one device is connected.
    """
    try:
        data = storage.read_channels(working_dir, name)
    except FileNotFoundError:
        print(f"No saved channel set named '{name}' in {working_dir}")
        return 1

    data = _decrypt_if_needed(data)
    if data is None:
        return 1

    port = _resolve_port(port)
    if port is None:
        return 1

    with device.open_device(port) as interface:
        device.import_channel_url(interface, data["channel_url"])
    print(f"Applied channel set '{name}' to device on {port}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "help":
        return run_help()
    if args.command == "scan":
        return run_scan()
    if args.command == "backup":
        return run_backup(args.working_dir, args.port, args.encrypt)
    if args.command == "restore":
        return run_restore(args.working_dir, args.port, args.file, args.node_id)
    if args.command == "list":
        return run_list(args.working_dir)
    if args.command == "device-backups":
        return run_device_backups(args.working_dir, args.port)
    if args.command == "export-channels":
        return run_export_channels(args.working_dir, args.port, args.name, args.encrypt)
    if args.command == "import-channels":
        return run_import_channels(args.working_dir, args.port, args.name)

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


def export_channels_entry_point(argv: list[str] | None = None) -> int:
    """Console-script shortcut for ``meshprogrammer export-channels``."""
    return _run_subcommand("export-channels", argv)


def import_channels_entry_point(argv: list[str] | None = None) -> int:
    """Console-script shortcut for ``meshprogrammer import-channels``."""
    return _run_subcommand("import-channels", argv)


if __name__ == "__main__":
    sys.exit(main())
