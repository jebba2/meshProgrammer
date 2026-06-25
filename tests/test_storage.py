from datetime import datetime, timezone
from pathlib import Path

import pytest

from meshprogrammer import storage


def test_device_dir_is_named_by_node_id(tmp_path: Path) -> None:
    result = storage.device_dir(tmp_path, "!a1b2c3d4")

    assert result == tmp_path / "!a1b2c3d4"


def test_backup_path_is_timestamped_json_under_device_dir(tmp_path: Path) -> None:
    timestamp = datetime(2026, 6, 24, 15, 30, 0, tzinfo=timezone.utc)

    result = storage.backup_path(tmp_path, "!a1b2c3d4", timestamp)

    assert result == tmp_path / "!a1b2c3d4" / "backup-20260624T153000Z.json"


def test_write_backup_creates_device_dir_and_file(tmp_path: Path) -> None:
    timestamp = datetime(2026, 6, 24, 15, 30, 0, tzinfo=timezone.utc)
    payload = {"owner": "Test Node"}

    written = storage.write_backup(tmp_path, "!a1b2c3d4", payload, timestamp)

    assert written.exists()
    assert storage.read_backup(written) == payload


def test_list_device_ids_returns_subdirectories_sorted(tmp_path: Path) -> None:
    (tmp_path / "!bbbbbbbb").mkdir()
    (tmp_path / "!aaaaaaaa").mkdir()
    (tmp_path / "not_a_dir.txt").write_text("ignore me")

    result = storage.list_device_ids(tmp_path)

    assert result == ["!aaaaaaaa", "!bbbbbbbb"]


def test_list_device_ids_on_missing_working_dir_returns_empty(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist"

    assert storage.list_device_ids(missing) == []


def test_list_backups_sorted_newest_first(tmp_path: Path) -> None:
    older = datetime(2026, 6, 24, 10, 0, 0, tzinfo=timezone.utc)
    newer = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)
    storage.write_backup(tmp_path, "!a1b2c3d4", {"v": 1}, older)
    storage.write_backup(tmp_path, "!a1b2c3d4", {"v": 2}, newer)

    result = storage.list_backups(tmp_path, "!a1b2c3d4")

    assert [p.name for p in result] == [
        "backup-20260624T120000Z.json",
        "backup-20260624T100000Z.json",
    ]


def test_list_backups_for_unknown_device_returns_empty(tmp_path: Path) -> None:
    assert storage.list_backups(tmp_path, "!unknown") == []


def test_latest_backup_returns_most_recent(tmp_path: Path) -> None:
    older = datetime(2026, 6, 24, 10, 0, 0, tzinfo=timezone.utc)
    newer = datetime(2026, 6, 24, 12, 0, 0, tzinfo=timezone.utc)
    storage.write_backup(tmp_path, "!a1b2c3d4", {"v": 1}, older)
    expected = storage.write_backup(tmp_path, "!a1b2c3d4", {"v": 2}, newer)

    assert storage.latest_backup(tmp_path, "!a1b2c3d4") == expected


def test_latest_backup_for_unknown_device_returns_none(tmp_path: Path) -> None:
    assert storage.latest_backup(tmp_path, "!unknown") is None


def test_channels_path_is_named_json_under_channels_subdir(tmp_path: Path) -> None:
    result = storage.channels_path(tmp_path, "office")

    assert result == tmp_path / "channels" / "office.json"


def test_write_channels_then_read_channels_round_trips(tmp_path: Path) -> None:
    written = storage.write_channels(tmp_path, "office", "https://meshtastic.org/e/#abc123")

    assert written.exists()
    assert storage.read_channels(tmp_path, "office") == "https://meshtastic.org/e/#abc123"


def test_read_channels_for_unknown_name_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        storage.read_channels(tmp_path, "missing")
