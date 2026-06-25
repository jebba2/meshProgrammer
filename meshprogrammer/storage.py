"""Filesystem layout for device config backups.

Backups live under a working directory, one subfolder per device (named by
the device's Meshtastic node id), with one timestamped JSON file per backup.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_WORKING_DIR = Path("working")

_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"


def device_dir(working_dir: Path, node_id: str) -> Path:
    """Return the per-device backup folder for ``node_id``."""
    return working_dir / node_id


def backup_path(working_dir: Path, node_id: str, timestamp: datetime) -> Path:
    """Return the path a backup taken at ``timestamp`` would be written to."""
    file_name = f"backup-{timestamp.strftime(_TIMESTAMP_FORMAT)}.json"
    return device_dir(working_dir, node_id) / file_name


def write_backup(
    working_dir: Path, node_id: str, payload: dict[str, Any], timestamp: datetime
) -> Path:
    """Write ``payload`` as a new timestamped backup for ``node_id``.

    Returns the path the backup was written to.
    """
    path = backup_path(working_dir, node_id, timestamp)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    return path


def read_backup(path: Path) -> dict[str, Any]:
    """Read a backup JSON file back into a dict."""
    return json.loads(path.read_text())


def list_device_ids(working_dir: Path) -> list[str]:
    """Return all known device ids, sorted, or [] if the working dir doesn't exist."""
    if not working_dir.is_dir():
        return []
    return sorted(p.name for p in working_dir.iterdir() if p.is_dir())


def list_backups(working_dir: Path, node_id: str) -> list[Path]:
    """Return all backups for ``node_id``, newest first."""
    folder = device_dir(working_dir, node_id)
    if not folder.is_dir():
        return []
    return sorted(folder.glob("backup-*.json"), reverse=True)


def latest_backup(working_dir: Path, node_id: str) -> Path | None:
    """Return the most recent backup for ``node_id``, or None if there isn't one."""
    backups = list_backups(working_dir, node_id)
    return backups[0] if backups else None
