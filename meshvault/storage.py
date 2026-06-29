"""Filesystem layout for device config backups and shared channel sets.

Backups live under a working directory, one subfolder per device (named by
the device's Meshtastic node id), with one timestamped JSON file per backup.

Channel sets are not tied to one device -- they're meant to be shared across
many -- so they live under a single ``channels`` subfolder, one named JSON
file per saved set.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from meshvault.crypto import is_encrypted

DEFAULT_WORKING_DIR = Path("working")

_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"
_TIMESTAMP_RE = re.compile(r"\d{8}T\d{6}Z")


def device_dir(working_dir: Path, node_id: str) -> Path:
    """Return the per-device backup folder for ``node_id``."""
    return working_dir / node_id


def backup_path(
    working_dir: Path, node_id: str, timestamp: datetime, encrypted: bool = False
) -> Path:
    """Return the path a backup taken at ``timestamp`` would be written to.

    Encrypted backups get an ``encryptedbackup-`` prefix instead of
    ``backup-`` so they're identifiable by filename alone.
    """
    prefix = "encryptedbackup" if encrypted else "backup"
    file_name = f"{prefix}-{timestamp.strftime(_TIMESTAMP_FORMAT)}.json"
    return device_dir(working_dir, node_id) / file_name


def write_backup(
    working_dir: Path, node_id: str, payload: dict[str, Any], timestamp: datetime
) -> Path:
    """Write ``payload`` as a new timestamped backup for ``node_id``.

    Returns the path the backup was written to.
    """
    path = backup_path(working_dir, node_id, timestamp, encrypted=is_encrypted(payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return path


def read_backup(path: Path) -> dict[str, Any]:
    """Read a backup JSON file back into a dict."""
    return json.loads(path.read_text())


def list_device_ids(working_dir: Path) -> list[str]:
    """Return all known device ids, sorted, or [] if the working dir doesn't exist.

    Device ids are folder names starting with "!" (the Meshtastic node id
    format), which excludes the "channels" subfolder used for shared
    channel sets.
    """
    if not working_dir.is_dir():
        return []
    return sorted(
        p.name for p in working_dir.iterdir() if p.is_dir() and p.name.startswith("!")
    )


def _timestamp_sort_key(path: Path) -> str:
    """Sort key based on the embedded timestamp, not the raw filename.

    Plain ("backup-...") and encrypted ("encryptedbackup-...") backups have
    different prefixes, so sorting by filename string would group all
    "backup-" files before all "encryptedbackup-" files regardless of which
    is actually newer. Sorting by the embedded timestamp avoids that.
    """
    match = _TIMESTAMP_RE.search(path.name)
    return match.group() if match else path.name


def list_backups(working_dir: Path, node_id: str) -> list[Path]:
    """Return all backups (plain and encrypted) for ``node_id``, newest first."""
    folder = device_dir(working_dir, node_id)
    if not folder.is_dir():
        return []
    return sorted(folder.glob("*backup-*.json"), key=_timestamp_sort_key, reverse=True)


def latest_backup(working_dir: Path, node_id: str) -> Path | None:
    """Return the most recent backup for ``node_id``, or None if there isn't one."""
    backups = list_backups(working_dir, node_id)
    return backups[0] if backups else None


def channels_path(working_dir: Path, name: str) -> Path:
    """Return the path a saved channel set named ``name`` would be written to."""
    return working_dir / "channels" / f"{name}.json"


def write_channels(working_dir: Path, name: str, payload: dict[str, Any]) -> Path:
    """Save ``payload`` (e.g. ``{"channel_url": ...}``, plain or encrypted) as a named,
    sharable channel set.

    Returns the path it was written to.
    """
    path = channels_path(working_dir, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return path


def read_channels(working_dir: Path, name: str) -> dict[str, Any]:
    """Return the payload dict previously saved as ``name``."""
    path = channels_path(working_dir, name)
    return json.loads(path.read_text())


def list_channel_names(working_dir: Path) -> list[str]:
    """Return all known channel set names, sorted, or [] if there are none."""
    folder = working_dir / "channels"
    if not folder.is_dir():
        return []
    return sorted(p.stem for p in folder.glob("*.json"))
