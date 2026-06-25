from meshtastic.protobuf import localonly_pb2

from meshprogrammer import backup


def _sample_local_config() -> localonly_pb2.LocalConfig:
    config = localonly_pb2.LocalConfig()
    config.device.role = 1
    config.lora.region = 2
    return config


def _sample_module_config() -> localonly_pb2.LocalModuleConfig:
    config = localonly_pb2.LocalModuleConfig()
    config.mqtt.enabled = True
    config.telemetry.device_update_interval = 900
    return config


def test_build_backup_payload_contains_identifying_fields() -> None:
    payload = backup.build_backup_payload(
        node_id="!a1b2c3d4",
        long_name="Base Camp",
        short_name="BC",
        channel_url="https://meshtastic.org/e/#abc123",
        local_config=_sample_local_config(),
        module_config=_sample_module_config(),
    )

    assert payload["node_id"] == "!a1b2c3d4"
    assert payload["long_name"] == "Base Camp"
    assert payload["short_name"] == "BC"
    assert payload["channel_url"] == "https://meshtastic.org/e/#abc123"
    assert payload["local_config"]["device"]["role"] == "CLIENT_MUTE"
    assert payload["module_config"]["mqtt"]["enabled"] is True


def test_payload_round_trips_through_parse_backup_payload() -> None:
    local_config = _sample_local_config()
    module_config = _sample_module_config()
    payload = backup.build_backup_payload(
        node_id="!a1b2c3d4",
        long_name="Base Camp",
        short_name="BC",
        channel_url="https://meshtastic.org/e/#abc123",
        local_config=local_config,
        module_config=module_config,
    )

    parsed = backup.parse_backup_payload(payload)

    assert parsed.node_id == "!a1b2c3d4"
    assert parsed.long_name == "Base Camp"
    assert parsed.short_name == "BC"
    assert parsed.channel_url == "https://meshtastic.org/e/#abc123"
    assert parsed.local_config == local_config
    assert parsed.module_config == module_config


def test_build_backup_payload_omits_unset_owner_and_channel_fields() -> None:
    payload = backup.build_backup_payload(
        node_id="!a1b2c3d4",
        long_name=None,
        short_name=None,
        channel_url=None,
        local_config=_sample_local_config(),
        module_config=_sample_module_config(),
    )

    assert "long_name" not in payload
    assert "short_name" not in payload
    assert "channel_url" not in payload


def test_parse_backup_payload_handles_missing_owner_and_channel_fields() -> None:
    payload = backup.build_backup_payload(
        node_id="!a1b2c3d4",
        long_name=None,
        short_name=None,
        channel_url=None,
        local_config=_sample_local_config(),
        module_config=_sample_module_config(),
    )

    parsed = backup.parse_backup_payload(payload)

    assert parsed.long_name is None
    assert parsed.short_name is None
    assert parsed.channel_url is None
