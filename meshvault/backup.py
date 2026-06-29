"""Lossless JSON serialization of a device's config protobufs.

Round-trips ``LocalConfig``/``LocalModuleConfig`` straight through
``google.protobuf.json_format`` rather than the human-editable YAML shape
used by the ``meshtastic`` CLI's ``--export-config`` — we're restoring a
device's own settings, not hand-editing them, so the simpler lossless
mapping is enough.
"""

from dataclasses import dataclass
from typing import Any

from google.protobuf.json_format import MessageToDict, ParseDict
from meshtastic.protobuf import localonly_pb2


@dataclass
class BackupData:
    node_id: str
    long_name: str | None
    short_name: str | None
    channel_url: str | None
    local_config: localonly_pb2.LocalConfig
    module_config: localonly_pb2.LocalModuleConfig


def build_backup_payload(
    node_id: str,
    long_name: str | None,
    short_name: str | None,
    channel_url: str | None,
    local_config: localonly_pb2.LocalConfig,
    module_config: localonly_pb2.LocalModuleConfig,
) -> dict[str, Any]:
    """Build a JSON-serializable backup payload for one device."""
    payload: dict[str, Any] = {
        "node_id": node_id,
        "local_config": MessageToDict(local_config),
        "module_config": MessageToDict(module_config),
    }
    if long_name is not None:
        payload["long_name"] = long_name
    if short_name is not None:
        payload["short_name"] = short_name
    if channel_url is not None:
        payload["channel_url"] = channel_url
    return payload


def parse_backup_payload(payload: dict[str, Any]) -> BackupData:
    """Parse a backup payload back into config protobufs and owner/channel info."""
    local_config = ParseDict(payload["local_config"], localonly_pb2.LocalConfig())
    module_config = ParseDict(payload["module_config"], localonly_pb2.LocalModuleConfig())
    return BackupData(
        node_id=payload["node_id"],
        long_name=payload.get("long_name"),
        short_name=payload.get("short_name"),
        channel_url=payload.get("channel_url"),
        local_config=local_config,
        module_config=module_config,
    )
