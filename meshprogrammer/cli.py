"""Command-line interface for backing up and restoring Meshtastic device configs."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from meshtastic.serial_interface import SerialInterface

from meshprogrammer import backup as backup_module
from meshprogrammer import device, storage


def _add_working_dir_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--working-dir",
        type=Path,
        default=storage.DEFAULT_WORKING_DIR,
        help="Folder to store/read device config backups (default: %(default)s)",
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
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("scan", help="List connected Meshtastic serial devices")

    backup_parser = subparsers.add_parser("backup", help="Back up a connected device's config")
    _add_working_dir_arg(backup_parser)
    backup_parser.add_argument(
        "--port", required=True, help="Serial port the device is connected on, e.g. COM3"
    )

    restore_parser = subparsers.add_parser("restore", help="Restore a backup onto a connected device")
    _add_working_dir_arg(restore_parser)
    restore_parser.add_argument(
        "--port", required=True, help="Serial port the device is connected on, e.g. COM3"
    )
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

    return parser


def run_scan() -> int:
    """List connected Meshtastic serial devices."""
    ports = device.scan_ports()
    if not ports:
        print("No Meshtastic devices detected.")
        return 0
    for port in ports:
        print(port)
    return 0


def run_backup(working_dir: Path, port: str) -> int:
    """Back up the config of the device connected on ``port``."""
    with device.open_device(port) as interface:
        payload = device.backup_from_interface(interface)
    node_id = payload["node_id"]
    timestamp = datetime.now(timezone.utc)
    path = storage.write_backup(working_dir, node_id, payload, timestamp)
    print(f"Backed up {node_id} to {path}")
    return 0


def _apply_restore(interface: SerialInterface, backup_path: Path) -> None:
    payload = storage.read_backup(backup_path)
    parsed = backup_module.parse_backup_payload(payload)
    device.restore_to_interface(interface, parsed)
    print(f"Restored {backup_path} to device")


def run_restore(working_dir: Path, port: str, file: Path | None, node_id: str | None) -> int:
    """Restore a backup onto the device connected on ``port``.

    If ``file`` is given, restore that exact backup. Otherwise restore the
    latest backup for ``node_id``, or for the connected device's own node id
    if ``node_id`` is also not given.
    """
    if file is not None:
        with device.open_device(port) as interface:
            _apply_restore(interface, file)
        return 0

    with device.open_device(port) as interface:
        target_node_id = node_id or device.get_node_id(interface)
        backup_path = storage.latest_backup(working_dir, target_node_id)
        if backup_path is None:
            print(f"No backups found for {target_node_id} in {working_dir}")
            return 1
        _apply_restore(interface, backup_path)
    return 0


def run_list(working_dir: Path) -> int:
    """Print known devices and their backups."""
    device_ids = storage.list_device_ids(working_dir)
    if not device_ids:
        print(f"No backups found in {working_dir}")
        return 0
    for node_id in device_ids:
        backups = storage.list_backups(working_dir, node_id)
        suffix = "" if len(backups) == 1 else "s"
        print(f"{node_id} ({len(backups)} backup{suffix})")
        for backup_file in backups:
            print(f"  {backup_file.name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan":
        return run_scan()
    if args.command == "backup":
        return run_backup(args.working_dir, args.port)
    if args.command == "restore":
        return run_restore(args.working_dir, args.port, args.file, args.node_id)
    if args.command == "list":
        return run_list(args.working_dir)

    parser.error(f"Unknown command: {args.command}")
    return 1


def _run_subcommand(subcommand: str, argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    return main([subcommand, *argv])


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


if __name__ == "__main__":
    sys.exit(main())
