from datetime import datetime, timezone
from pathlib import Path

import pytest
from meshtastic.protobuf import localonly_pb2

from meshprogrammer import backup as backup_module
from meshprogrammer import cli, crypto, storage


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


def test_build_parser_backup_requires_port() -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["backup"])


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


def test_scan_entry_point_rejects_working_dir() -> None:
    with pytest.raises(SystemExit):
        cli.scan_entry_point(["--working-dir", "/tmp/foo"])


def test_backup_entry_point_requires_port() -> None:
    with pytest.raises(SystemExit):
        cli.backup_entry_point([])


def test_restore_entry_point_requires_port() -> None:
    with pytest.raises(SystemExit):
        cli.restore_entry_point([])


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


def test_build_parser_export_channels_requires_port() -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["export-channels", "office"])


def test_build_parser_export_channels_parses_port_and_name() -> None:
    parser = cli.build_parser()

    args = parser.parse_args(["export-channels", "--port", "COM3", "office"])

    assert args.command == "export-channels"
    assert args.port == "COM3"
    assert args.name == "office"


def test_build_parser_import_channels_requires_port() -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["import-channels", "office"])


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


def test_export_channels_entry_point_requires_port() -> None:
    with pytest.raises(SystemExit):
        cli.export_channels_entry_point(["office"])


def test_import_channels_entry_point_requires_port() -> None:
    with pytest.raises(SystemExit):
        cli.import_channels_entry_point(["office"])


def test_run_import_channels_reports_missing_channel_set(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = cli.run_import_channels(tmp_path, "COM3", "missing")

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

    result = cli.run_import_channels(tmp_path, "COM3", "office")

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
