from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest
from meshtastic.protobuf import localonly_pb2

from meshprogrammer import backup as backup_module
from meshprogrammer import cli, crypto, storage


@contextmanager
def _fake_open_device(_port: str | None = None, _ble: str | None = None):
    yield object()


def test_build_parser_defaults_working_dir() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["list"])

    assert args.working_dir == storage.DEFAULT_WORKING_DIR
    assert args.command == "list"


def test_build_parser_accepts_custom_working_dir_after_subcommand() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["list", "--working-dir", "/tmp/foo"])

    assert args.working_dir == Path("/tmp/foo")


def test_build_parser_scan_does_not_accept_working_dir() -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["scan", "--working-dir", "/tmp/foo"])


def test_build_parser_backup_accepts_working_dir() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["backup", "--port", "COM3", "--working-dir", "/tmp/foo"])

    assert args.working_dir == Path("/tmp/foo")


def test_build_parser_restore_accepts_working_dir() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["restore", "--port", "COM3", "--working-dir", "/tmp/foo"])

    assert args.working_dir == Path("/tmp/foo")


def test_build_parser_backup_port_defaults_to_none() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["backup"])

    assert args.port is None


def test_build_parser_backup_parses_port() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["backup", "--port", "COM3"])

    assert args.command == "backup"
    assert args.port == "COM3"


def test_build_parser_restore_file_and_node_id_are_mutually_exclusive() -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            ["restore", "--port", "COM3", "--file", "a.json", "--node-id", "!abc"]
        )


def test_build_parser_restore_defaults_file_and_node_id_to_none() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["restore", "--port", "COM3"])

    assert args.file is None
    assert args.node_id is None


_CONNECTION_COMMANDS = [
    pytest.param(["backup"], id="backup"),
    pytest.param(["restore"], id="restore"),
    pytest.param(["device-backups"], id="device-backups"),
    pytest.param(["export-channels", "office"], id="export-channels"),
    pytest.param(["import-channels", "office"], id="import-channels"),
]


@pytest.mark.parametrize("command_args", _CONNECTION_COMMANDS)
def test_build_parser_ble_defaults_to_none(command_args: list[str]) -> None:
    parser = cli.build_parser()

    args = parser.parse_args(command_args)

    assert args.ble is None


@pytest.mark.parametrize("command_args", _CONNECTION_COMMANDS)
def test_build_parser_ble_flag_without_value_defaults_to_any(command_args: list[str]) -> None:
    parser = cli.build_parser()

    args = parser.parse_args([*command_args, "--ble"])

    assert args.ble == "any"


@pytest.mark.parametrize("command_args", _CONNECTION_COMMANDS)
def test_build_parser_ble_flag_accepts_device_name(command_args: list[str]) -> None:
    parser = cli.build_parser()

    args = parser.parse_args([*command_args, "--ble", "Jeba 325c"])

    assert args.ble == "Jeba 325c"


@pytest.mark.parametrize("command_args", _CONNECTION_COMMANDS)
def test_build_parser_port_and_ble_are_mutually_exclusive(command_args: list[str]) -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args([*command_args, "--port", "COM3", "--ble"])


def test_build_parser_scan_accepts_ble_flag() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["scan", "--ble"])

    assert args.ble is True


def test_build_parser_scan_ble_defaults_false() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["scan"])

    assert args.ble is False


def test_scan_entry_point_rejects_working_dir() -> None:
    with pytest.raises(SystemExit):
        cli.scan_entry_point(["--working-dir", "/tmp/foo"])


def test_backup_entry_point_without_port_or_device_reports_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.device, "scan_ports", lambda: [])

    result = cli.backup_entry_point([])

    assert result == 1
    assert "No Meshtastic devices detected" in capsys.readouterr().out


def test_restore_entry_point_without_port_or_device_reports_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.device, "scan_ports", lambda: [])

    result = cli.restore_entry_point([])

    assert result == 1
    assert "No Meshtastic devices detected" in capsys.readouterr().out


def test_list_entry_point_rejects_unknown_args() -> None:
    with pytest.raises(SystemExit):
        cli.list_entry_point(["--bogus"])


def test_list_entry_point_accepts_working_dir(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    result = cli.list_entry_point(["--working-dir", str(tmp_path)])

    assert result == 0
    assert "No backups found" in capsys.readouterr().out


def test_run_list_with_no_backups_returns_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    result = cli.run_list(tmp_path)

    assert result == 0
    assert "No backups found" in capsys.readouterr().out


def test_run_list_prints_devices_and_backup_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    timestamp = datetime(2026, 6, 24, 15, 30, 0, tzinfo=timezone.utc)
    storage.write_backup(tmp_path, "!a1b2c3d4", {"v": 1}, timestamp)

    result = cli.run_list(tmp_path)
    out = capsys.readouterr().out

    assert result == 0
    assert "!a1b2c3d4" in out
    assert "backup-20260624T153000Z.json" in out


def test_build_parser_export_channels_port_defaults_to_none() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["export-channels", "office"])

    assert args.port is None


def test_build_parser_export_channels_parses_port_and_name() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["export-channels", "--port", "COM3", "office"])

    assert args.command == "export-channels"
    assert args.port == "COM3"
    assert args.name == "office"


def test_build_parser_import_channels_port_defaults_to_none() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["import-channels", "office"])

    assert args.port is None


def test_build_parser_import_channels_parses_port_and_name() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["import-channels", "--port", "COM3", "office"])

    assert args.command == "import-channels"
    assert args.port == "COM3"
    assert args.name == "office"


def test_build_parser_export_channels_accepts_working_dir() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(
        ["export-channels", "--port", "COM3", "--working-dir", "/tmp/foo", "office"]
    )

    assert args.working_dir == Path("/tmp/foo")


def test_export_channels_entry_point_without_port_or_device_reports_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.device, "scan_ports", lambda: [])

    result = cli.export_channels_entry_point(["office"])

    assert result == 1
    assert "No Meshtastic devices detected" in capsys.readouterr().out


def test_import_channels_entry_point_without_port_or_device_reports_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    storage.write_channels(tmp_path, "office", {"channel_url": "https://example"})
    monkeypatch.setattr(cli.device, "scan_ports", lambda: [])

    result = cli.import_channels_entry_point(["--working-dir", str(tmp_path), "office"])

    assert result == 1
    assert "No Meshtastic devices detected" in capsys.readouterr().out


def test_run_import_channels_reports_missing_channel_set(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = cli.run_import_channels(tmp_path, "COM3", None, "missing")

    assert result == 1
    assert "No saved channel set named 'missing'" in capsys.readouterr().out


def test_build_parser_backup_accepts_encrypt_flag() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["backup", "--port", "COM3", "--encrypt"])

    assert args.encrypt is True


def test_build_parser_backup_encrypt_defaults_false() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["backup", "--port", "COM3"])

    assert args.encrypt is False


def test_build_parser_export_channels_accepts_encrypt_flag() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["export-channels", "--port", "COM3", "--encrypt", "office"])

    assert args.encrypt is True


def test_prompt_new_password_retries_on_mismatch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    responses = iter(["first", "second", "match", "match"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_a, **_k: next(responses))

    result = cli._prompt_new_password()

    assert result == "match"
    assert "did not match" in capsys.readouterr().out


def test_prompt_new_password_rejects_empty_password(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter(["", "ok", "ok"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_a, **_k: next(responses))

    assert cli._prompt_new_password() == "ok"


def test_decrypt_if_needed_passes_through_plain_payload() -> None:
    assert cli._decrypt_if_needed({"channel_url": "x"}) == {"channel_url": "x"}


def test_decrypt_if_needed_prompts_and_decrypts(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"channel_url": "https://example"}
    envelope = crypto.encrypt_payload(payload, "secret")
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_a, **_k: "secret")

    assert cli._decrypt_if_needed(envelope) == payload


def test_decrypt_if_needed_returns_none_on_wrong_password(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    envelope = crypto.encrypt_payload({"channel_url": "x"}, "secret")
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_a, **_k: "nope")

    assert cli._decrypt_if_needed(envelope) is None
    assert "Incorrect password" in capsys.readouterr().out


def test_run_import_channels_returns_one_on_wrong_password(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    envelope = crypto.encrypt_payload({"channel_url": "https://example"}, "right")
    storage.write_channels(tmp_path, "office", envelope)
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_a, **_k: "wrong")

    result = cli.run_import_channels(tmp_path, "COM3", None, "office")

    assert result == 1
    assert "Incorrect password" in capsys.readouterr().out


def test_apply_restore_decrypts_encrypted_backup_before_restoring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = backup_module.build_backup_payload(
        node_id="!a1b2c3d4",
        long_name=None,
        short_name=None,
        channel_url=None,
        local_config=localonly_pb2.LocalConfig(),
        module_config=localonly_pb2.LocalModuleConfig(),
    )
    envelope = crypto.encrypt_payload(payload, "secret")
    path = storage.write_backup(tmp_path, "!a1b2c3d4", envelope, datetime.now(timezone.utc))
    monkeypatch.setattr(cli.getpass, "getpass", lambda *_a, **_k: "secret")
    restored: dict[str, object] = {}
    monkeypatch.setattr(
        cli.device,
        "restore_to_interface",
        lambda _interface, backup: restored.setdefault("backup", backup),
    )

    result = cli._apply_restore(object(), path)  # interface unused by the stub above

    assert result is True
    assert restored["backup"].node_id == "!a1b2c3d4"


def test_resolve_port_returns_explicit_port_without_scanning(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail_if_called() -> list[str]:
        raise AssertionError("should not scan when --port was given explicitly")

    monkeypatch.setattr(cli.device, "scan_ports", _fail_if_called)

    assert cli._resolve_port("COM3") == "COM3"


def test_resolve_port_auto_detects_single_device(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli.device, "scan_ports", lambda: ["COM5"])

    assert cli._resolve_port(None) == "COM5"


def test_resolve_port_returns_none_when_no_devices(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.device, "scan_ports", lambda: [])

    result = cli._resolve_port(None)

    assert result is None
    assert "No Meshtastic devices detected" in capsys.readouterr().out


def test_resolve_port_returns_none_when_multiple_devices(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.device, "scan_ports", lambda: ["COM3", "COM5"])

    result = cli._resolve_port(None)
    out = capsys.readouterr().out

    assert result is None
    assert "COM3" in out
    assert "COM5" in out


def test_run_backup_returns_one_without_opening_device_when_port_unresolved(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.device, "scan_ports", lambda: [])
    monkeypatch.setattr(
        cli.device, "open_device", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("opened device"))
    )

    result = cli.run_backup(Path("working"), None, None, False)

    assert result == 1
    assert "No Meshtastic devices detected" in capsys.readouterr().out


def test_run_restore_returns_one_without_opening_device_when_port_unresolved(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.device, "scan_ports", lambda: [])
    monkeypatch.setattr(
        cli.device, "open_device", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("opened device"))
    )

    result = cli.run_restore(Path("working"), None, None, None, None)

    assert result == 1
    assert "No Meshtastic devices detected" in capsys.readouterr().out


def test_run_export_channels_returns_one_without_opening_device_when_port_unresolved(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.device, "scan_ports", lambda: [])
    monkeypatch.setattr(
        cli.device, "open_device", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("opened device"))
    )

    result = cli.run_export_channels(Path("working"), None, None, "office", False)

    assert result == 1
    assert "No Meshtastic devices detected" in capsys.readouterr().out


def test_run_import_channels_returns_one_without_opening_device_when_port_unresolved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    storage.write_channels(tmp_path, "office", {"channel_url": "https://example"})
    monkeypatch.setattr(cli.device, "scan_ports", lambda: [])
    monkeypatch.setattr(
        cli.device, "open_device", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("opened device"))
    )

    result = cli.run_import_channels(tmp_path, None, None, "office")

    assert result == 1
    assert "No Meshtastic devices detected" in capsys.readouterr().out


def test_build_parser_device_backups_port_defaults_to_none() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["device-backups"])

    assert args.command == "device-backups"
    assert args.port is None


def test_build_parser_device_backups_accepts_port_and_working_dir() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(
        ["device-backups", "--port", "COM3", "--working-dir", "/tmp/foo"]
    )

    assert args.port == "COM3"
    assert args.working_dir == Path("/tmp/foo")


def test_run_device_backups_lists_backups_for_connected_device(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    timestamp = datetime(2026, 6, 24, 15, 30, 0, tzinfo=timezone.utc)
    storage.write_backup(tmp_path, "!a1b2c3d4", {"v": 1}, timestamp)
    monkeypatch.setattr(cli.device, "open_device", _fake_open_device)
    monkeypatch.setattr(cli.device, "get_node_id", lambda _interface: "!a1b2c3d4")

    result = cli.run_device_backups(tmp_path, "COM3", None)
    out = capsys.readouterr().out

    assert result == 0
    assert "!a1b2c3d4" in out
    assert "backup-20260624T153000Z.json" in out


def test_run_device_backups_with_no_backups_reports_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.device, "open_device", _fake_open_device)
    monkeypatch.setattr(cli.device, "get_node_id", lambda _interface: "!a1b2c3d4")

    result = cli.run_device_backups(tmp_path, "COM3", None)

    assert result == 0
    assert "No backups found for !a1b2c3d4" in capsys.readouterr().out


def test_run_device_backups_does_not_list_other_devices_backups(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    timestamp = datetime(2026, 6, 24, 15, 30, 0, tzinfo=timezone.utc)
    storage.write_backup(tmp_path, "!other00", {"v": 1}, timestamp)
    monkeypatch.setattr(cli.device, "open_device", _fake_open_device)
    monkeypatch.setattr(cli.device, "get_node_id", lambda _interface: "!a1b2c3d4")

    result = cli.run_device_backups(tmp_path, "COM3", None)
    out = capsys.readouterr().out

    assert result == 0
    assert "!other00" not in out


def test_run_device_backups_returns_one_without_opening_device_when_port_unresolved(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.device, "scan_ports", lambda: [])
    monkeypatch.setattr(
        cli.device, "open_device", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("opened device"))
    )

    result = cli.run_device_backups(Path("working"), None, None)

    assert result == 1
    assert "No Meshtastic devices detected" in capsys.readouterr().out


def test_device_backups_entry_point_without_port_or_device_reports_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.device, "scan_ports", lambda: [])

    result = cli.device_backups_entry_point([])

    assert result == 1
    assert "No Meshtastic devices detected" in capsys.readouterr().out


def test_build_parser_accepts_help_command() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["help"])

    assert args.command == "help"


def test_run_help_lists_every_command(capsys: pytest.CaptureFixture[str]) -> None:
    result = cli.run_help()
    out = capsys.readouterr().out

    assert result == 0
    for command in [
        "scan",
        "backup",
        "restore",
        "list",
        "device-backups",
        "export-channels",
        "import-channels",
        "help",
    ]:
        assert command in out


def test_help_entry_point_runs_without_error(capsys: pytest.CaptureFixture[str]) -> None:
    result = cli.help_entry_point([])

    assert result == 0
    assert "scan" in capsys.readouterr().out


def test_run_help_mentions_port_and_encrypt_options(capsys: pytest.CaptureFixture[str]) -> None:
    cli.run_help()
    out = capsys.readouterr().out

    assert "--port" in out
    assert "--encrypt" in out


def test_build_parser_list_channels_accepts_working_dir() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["list-channels", "--working-dir", "/tmp/foo"])

    assert args.command == "list-channels"
    assert args.working_dir == Path("/tmp/foo")


def test_run_list_channels_with_none_reports_empty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = cli.run_list_channels(tmp_path)

    assert result == 0
    assert "No channel sets found" in capsys.readouterr().out


def test_run_list_channels_lists_plain_names(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    storage.write_channels(tmp_path, "office", {"channel_url": "https://example"})

    result = cli.run_list_channels(tmp_path)
    out = capsys.readouterr().out

    assert result == 0
    assert "office" in out
    assert "(encrypted)" not in out


def test_run_list_channels_marks_encrypted_sets(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    envelope = crypto.encrypt_payload({"channel_url": "https://example"}, "secret")
    storage.write_channels(tmp_path, "office", envelope)

    result = cli.run_list_channels(tmp_path)
    out = capsys.readouterr().out

    assert result == 0
    assert "office (encrypted)" in out


def test_list_channels_entry_point_accepts_working_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = cli.list_channels_entry_point(["--working-dir", str(tmp_path)])

    assert result == 0
    assert "No channel sets found" in capsys.readouterr().out


def test_run_help_mentions_ble_option(capsys: pytest.CaptureFixture[str]) -> None:
    cli.run_help()
    out = capsys.readouterr().out

    assert "--ble" in out


def test_run_scan_lists_serial_ports(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.device, "scan_ports", lambda: ["COM3", "COM5"])

    result = cli.run_scan(False)
    out = capsys.readouterr().out

    assert result == 0
    assert "COM3" in out
    assert "COM5" in out


def test_run_scan_with_no_serial_ports_reports_none(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.device, "scan_ports", lambda: [])

    result = cli.run_scan(False)

    assert result == 0
    assert "No Meshtastic devices detected." in capsys.readouterr().out


def test_run_scan_ble_lists_ble_devices(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.device, "scan_ble", lambda: ["Jeba 325c (AA:BB:CC:DD:EE:FF)"])
    monkeypatch.setattr(
        cli.device,
        "scan_ports",
        lambda: (_ for _ in ()).throw(AssertionError("should not scan serial ports when --ble given")),
    )

    result = cli.run_scan(True)
    out = capsys.readouterr().out

    assert result == 0
    assert "Jeba 325c (AA:BB:CC:DD:EE:FF)" in out


def test_run_scan_ble_with_no_devices_reports_none(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.device, "scan_ble", lambda: [])

    result = cli.run_scan(True)

    assert result == 0
    assert "No Meshtastic BLE devices detected." in capsys.readouterr().out


def test_main_scan_ble_dispatches_to_run_scan_with_ble_true(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli.device, "scan_ble", lambda: ["Jeba 325c (AA:BB:CC:DD:EE:FF)"])

    result = cli.main(["scan", "--ble"])

    assert result == 0
    assert "Jeba 325c (AA:BB:CC:DD:EE:FF)" in capsys.readouterr().out


def test_run_backup_uses_ble_without_resolving_port(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        cli.device,
        "scan_ports",
        lambda: (_ for _ in ()).throw(AssertionError("should not scan when --ble given")),
    )
    captured: dict[str, object] = {}

    @contextmanager
    def fake_open_device(port: str | None, ble: str | None):
        captured["port"] = port
        captured["ble"] = ble
        yield object()

    monkeypatch.setattr(cli.device, "open_device", fake_open_device)
    monkeypatch.setattr(cli.device, "backup_from_interface", lambda _i: {"node_id": "!abc"})

    result = cli.run_backup(tmp_path, None, "any", False)

    assert result == 0
    assert captured == {"port": None, "ble": "any"}


def test_run_restore_uses_ble_without_resolving_port(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    timestamp = datetime(2026, 6, 24, 15, 30, 0, tzinfo=timezone.utc)
    payload = backup_module.build_backup_payload(
        node_id="!a1b2c3d4",
        long_name=None,
        short_name=None,
        channel_url=None,
        local_config=localonly_pb2.LocalConfig(),
        module_config=localonly_pb2.LocalModuleConfig(),
    )
    storage.write_backup(tmp_path, "!a1b2c3d4", payload, timestamp)
    monkeypatch.setattr(
        cli.device,
        "scan_ports",
        lambda: (_ for _ in ()).throw(AssertionError("should not scan when --ble given")),
    )
    captured: dict[str, object] = {}

    @contextmanager
    def fake_open_device(port: str | None, ble: str | None):
        captured["port"] = port
        captured["ble"] = ble
        yield object()

    monkeypatch.setattr(cli.device, "open_device", fake_open_device)
    monkeypatch.setattr(cli.device, "get_node_id", lambda _i: "!a1b2c3d4")
    monkeypatch.setattr(cli.device, "restore_to_interface", lambda _i, _b: None)

    result = cli.run_restore(tmp_path, None, "any", None, None)

    assert result == 0
    assert captured == {"port": None, "ble": "any"}


def test_run_device_backups_uses_ble_without_resolving_port(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        cli.device,
        "scan_ports",
        lambda: (_ for _ in ()).throw(AssertionError("should not scan when --ble given")),
    )
    captured: dict[str, object] = {}

    @contextmanager
    def fake_open_device(port: str | None, ble: str | None):
        captured["port"] = port
        captured["ble"] = ble
        yield object()

    monkeypatch.setattr(cli.device, "open_device", fake_open_device)
    monkeypatch.setattr(cli.device, "get_node_id", lambda _i: "!abc")

    result = cli.run_device_backups(tmp_path, None, "Jeba 325c")

    assert result == 0
    assert captured == {"port": None, "ble": "Jeba 325c"}


def test_run_export_channels_uses_ble_without_resolving_port(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        cli.device,
        "scan_ports",
        lambda: (_ for _ in ()).throw(AssertionError("should not scan when --ble given")),
    )
    captured: dict[str, object] = {}

    @contextmanager
    def fake_open_device(port: str | None, ble: str | None):
        captured["port"] = port
        captured["ble"] = ble
        yield object()

    monkeypatch.setattr(cli.device, "open_device", fake_open_device)
    monkeypatch.setattr(cli.device, "export_channel_url", lambda _i: "https://example")

    result = cli.run_export_channels(tmp_path, None, "any", "office", False)

    assert result == 0
    assert captured == {"port": None, "ble": "any"}


def test_run_import_channels_uses_ble_without_resolving_port(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    storage.write_channels(tmp_path, "office", {"channel_url": "https://example"})
    monkeypatch.setattr(
        cli.device,
        "scan_ports",
        lambda: (_ for _ in ()).throw(AssertionError("should not scan when --ble given")),
    )
    captured: dict[str, object] = {}

    @contextmanager
    def fake_open_device(port: str | None, ble: str | None):
        captured["port"] = port
        captured["ble"] = ble
        yield object()

    monkeypatch.setattr(cli.device, "open_device", fake_open_device)
    monkeypatch.setattr(cli.device, "import_channel_url", lambda _i, _url: None)

    result = cli.run_import_channels(tmp_path, None, "any", "office")

    assert result == 0
    assert captured == {"port": None, "ble": "any"}
