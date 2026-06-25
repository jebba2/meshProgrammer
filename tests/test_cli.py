from datetime import datetime, timezone
from pathlib import Path

import pytest

from meshprogrammer import cli, storage


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
