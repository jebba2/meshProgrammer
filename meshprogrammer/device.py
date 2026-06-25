"""Thin adapter over the meshtastic library's live device I/O.

This module touches real hardware (USB serial) and is intentionally minimal:
all of the testable logic (working-dir layout, payload serialization) lives
in storage.py and backup.py. There are no automated tests here, since the
project's testing rules forbid mocking the real device API — this module
must be exercised against an actual Meshtastic device.

Field name lists below (LOCAL_CONFIG_FIELDS, MODULE_CONFIG_FIELDS) match the
branches handled by meshtastic.node.Node.writeConfig() in this installed
library version (meshtastic==2.7.9); "version" is excluded because
writeConfig() has no branch for it.
"""

from collections.abc import Iterator
from contextlib import contextmanager

import meshtastic.util
from meshtastic.serial_interface import SerialInterface

from meshprogrammer.backup import BackupData, build_backup_payload

LOCAL_CONFIG_FIELDS = [
    "device",
    "position",
    "power",
    "network",
    "display",
    "lora",
    "bluetooth",
    "security",
]

MODULE_CONFIG_FIELDS = [
    "mqtt",
    "serial",
    "external_notification",
    "store_forward",
    "range_test",
    "telemetry",
    "canned_message",
    "audio",
    "remote_hardware",
    "neighbor_info",
    "detection_sensor",
    "ambient_lighting",
    "paxcounter",
    "traffic_management",
]


def scan_ports() -> list[str]:
    """Return serial ports that look like they have a Meshtastic device attached."""
    return meshtastic.util.findPorts(eliminate_duplicates=True)


@contextmanager
def open_device(port: str) -> Iterator[SerialInterface]:
    """Open a serial connection to the device at ``port``, closing it on exit."""
    interface = SerialInterface(devPath=port)
    try:
        yield interface
    finally:
        interface.close()


def get_node_id(interface: SerialInterface) -> str:
    """Return the connected device's own node id, e.g. ``!a1b2c3d4``."""
    info = interface.getMyNodeInfo()
    if not info or "user" not in info or "id" not in info["user"]:
        raise RuntimeError("Connected device has no node id yet (no user info received)")
    return info["user"]["id"]


def backup_from_interface(interface: SerialInterface) -> dict:
    """Read the connected device's config into a JSON-serializable backup payload."""
    node = interface.localNode
    return build_backup_payload(
        node_id=get_node_id(interface),
        long_name=interface.getLongName(),
        short_name=interface.getShortName(),
        channel_url=node.getURL(),
        local_config=node.localConfig,
        module_config=node.moduleConfig,
    )


def restore_to_interface(interface: SerialInterface, backup: BackupData) -> None:
    """Write a previously captured backup back onto the connected device."""
    node = interface.localNode
    node.localConfig = backup.local_config
    node.moduleConfig = backup.module_config

    node.beginSettingsTransaction()
    for field in LOCAL_CONFIG_FIELDS + MODULE_CONFIG_FIELDS:
        node.writeConfig(field)
    node.commitSettingsTransaction()

    if backup.long_name is not None or backup.short_name is not None:
        node.setOwner(long_name=backup.long_name, short_name=backup.short_name)

    if backup.channel_url is not None:
        node.setURL(backup.channel_url)


def export_channel_url(interface: SerialInterface) -> str:
    """Return the connected device's channels as a sharable channel URL."""
    return interface.localNode.getURL(includeAll=True)


def import_channel_url(interface: SerialInterface, channel_url: str) -> None:
    """Apply a channel URL to the connected device, overwriting its current channels.

    Matches the same overwrite-by-index behavior as scanning a channel QR
    code in the official Meshtastic app, or running its CLI's --seturl: any
    channel beyond the saved set's count is left as-is, not disabled.
    """
    interface.localNode.setURL(channel_url, addOnly=False)
