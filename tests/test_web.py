from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest
from flask.testing import FlaskClient

from meshvault import crypto, storage
from meshvault.web import app as web_app


@contextmanager
def _fake_open_device(_port: str | None = None, _ble: str | None = None):
    yield object()


@pytest.fixture
def client(tmp_path: Path) -> FlaskClient:
    return web_app.create_app(tmp_path).test_client()


def test_index_returns_html(client: FlaskClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert b"<html" in response.data.lower()


def test_scan_serial_returns_ports(client: FlaskClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_app.device, "scan_ports", lambda: ["COM3", "COM5"])

    response = client.get("/api/scan")

    assert response.get_json() == {"ok": True, "ports": ["COM3", "COM5"]}


def test_scan_ble_returns_devices(client: FlaskClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_app.device, "scan_ble", lambda: ["Jeba 325c (AA:BB)"])

    response = client.get("/api/scan?ble=1")

    assert response.get_json() == {"ok": True, "ble_devices": ["Jeba 325c (AA:BB)"]}


def test_list_returns_devices_and_backups(client: FlaskClient, tmp_path: Path) -> None:
    storage.write_backup(tmp_path, "!a1b2c3d4", {"node_id": "!a1b2c3d4"}, datetime(2026, 1, 1, tzinfo=timezone.utc))

    response = client.get("/api/list")
    data = response.get_json()

    assert data["ok"] is True
    assert data["devices"] == [
        {"node_id": "!a1b2c3d4", "backups": ["backup-20260101T000000Z.json"]}
    ]


def test_list_empty_when_no_backups(client: FlaskClient) -> None:
    response = client.get("/api/list")

    assert response.get_json() == {"ok": True, "devices": []}


def test_list_channels_returns_names_with_encrypted_flag(client: FlaskClient, tmp_path: Path) -> None:
    storage.write_channels(tmp_path, "office", {"channel_url": "https://x"})
    storage.write_channels(tmp_path, "secret", crypto.encrypt_payload({"channel_url": "https://y"}, "pw"))

    response = client.get("/api/list-channels")
    data = response.get_json()

    assert data["ok"] is True
    assert sorted(data["channel_sets"], key=lambda c: c["name"]) == [
        {"name": "office", "encrypted": False},
        {"name": "secret", "encrypted": True},
    ]


def test_backup_writes_plain_backup(
    client: FlaskClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(web_app.device, "open_device", _fake_open_device)
    monkeypatch.setattr(
        web_app.device, "backup_from_interface", lambda _interface: {"node_id": "!a1b2c3d4"}
    )

    response = client.post("/api/backup", json={"port": "COM3"})
    data = response.get_json()

    assert data["ok"] is True
    assert data["node_id"] == "!a1b2c3d4"
    assert storage.list_backups(tmp_path, "!a1b2c3d4") != []


def test_backup_writes_encrypted_backup_with_password(
    client: FlaskClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(web_app.device, "open_device", _fake_open_device)
    monkeypatch.setattr(
        web_app.device, "backup_from_interface", lambda _interface: {"node_id": "!a1b2c3d4"}
    )

    response = client.post("/api/backup", json={"port": "COM3", "encrypt": True, "password": "secret"})
    data = response.get_json()

    assert data["ok"] is True
    [backup_file] = storage.list_backups(tmp_path, "!a1b2c3d4")
    assert crypto.is_encrypted(storage.read_backup(backup_file))


def test_backup_requires_password_when_encrypt_true(
    client: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        web_app.device, "open_device", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("opened device"))
    )

    response = client.post("/api/backup", json={"port": "COM3", "encrypt": True})
    data = response.get_json()

    assert data["ok"] is False
    assert "password" in data["error"].lower()


def test_backup_resolves_port_automatically(
    client: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(web_app.device, "scan_ports", lambda: ["COM5"])
    monkeypatch.setattr(web_app.device, "open_device", _fake_open_device)
    monkeypatch.setattr(
        web_app.device, "backup_from_interface", lambda _interface: {"node_id": "!a1b2c3d4"}
    )

    response = client.post("/api/backup", json={})

    assert response.get_json()["ok"] is True


def test_backup_returns_error_when_port_unresolved(
    client: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(web_app.device, "scan_ports", lambda: [])
    monkeypatch.setattr(
        web_app.device, "open_device", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("opened device"))
    )

    response = client.post("/api/backup", json={})
    data = response.get_json()

    assert data["ok"] is False
    assert "No Meshtastic devices detected" in data["error"]


def test_restore_with_filename_restores_plain_backup(
    client: FlaskClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from meshvault.backup import build_backup_payload
    from meshtastic.protobuf import localonly_pb2

    payload = build_backup_payload(
        "!a1b2c3d4", None, None, None, localonly_pb2.LocalConfig(), localonly_pb2.LocalModuleConfig()
    )
    path = storage.write_backup(tmp_path, "!a1b2c3d4", payload, datetime(2026, 1, 1, tzinfo=timezone.utc))

    monkeypatch.setattr(web_app.device, "open_device", _fake_open_device)
    restored: list[object] = []
    monkeypatch.setattr(
        web_app.device, "restore_to_interface", lambda _interface, data: restored.append(data)
    )

    response = client.post(
        "/api/restore", json={"port": "COM3", "node_id": "!a1b2c3d4", "filename": path.name}
    )
    data = response.get_json()

    assert data["ok"] is True
    assert len(restored) == 1


def test_restore_with_filename_needs_password_for_encrypted_backup(
    client: FlaskClient, tmp_path: Path
) -> None:
    storage.write_backup(
        tmp_path,
        "!a1b2c3d4",
        crypto.encrypt_payload({"node_id": "!a1b2c3d4"}, "secret"),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    [path] = storage.list_backups(tmp_path, "!a1b2c3d4")

    response = client.post(
        "/api/restore", json={"port": "COM3", "node_id": "!a1b2c3d4", "filename": path.name}
    )
    data = response.get_json()

    assert data["ok"] is False
    assert data["needs_password"] is True


def test_restore_with_filename_wrong_password_returns_needs_password(
    client: FlaskClient, tmp_path: Path
) -> None:
    storage.write_backup(
        tmp_path,
        "!a1b2c3d4",
        crypto.encrypt_payload({"node_id": "!a1b2c3d4"}, "secret"),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    [path] = storage.list_backups(tmp_path, "!a1b2c3d4")

    response = client.post(
        "/api/restore",
        json={"port": "COM3", "node_id": "!a1b2c3d4", "filename": path.name, "password": "nope"},
    )
    data = response.get_json()

    assert data["ok"] is False
    assert data["needs_password"] is True
    assert "Incorrect password" in data["error"]


def test_restore_with_filename_correct_password_succeeds(
    client: FlaskClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from meshvault.backup import build_backup_payload
    from meshtastic.protobuf import localonly_pb2

    payload = build_backup_payload(
        "!a1b2c3d4", None, None, None, localonly_pb2.LocalConfig(), localonly_pb2.LocalModuleConfig()
    )
    storage.write_backup(
        tmp_path, "!a1b2c3d4", crypto.encrypt_payload(payload, "secret"), datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    [path] = storage.list_backups(tmp_path, "!a1b2c3d4")

    monkeypatch.setattr(web_app.device, "open_device", _fake_open_device)
    monkeypatch.setattr(web_app.device, "restore_to_interface", lambda _interface, _data: None)

    response = client.post(
        "/api/restore",
        json={"port": "COM3", "node_id": "!a1b2c3d4", "filename": path.name, "password": "secret"},
    )

    assert response.get_json()["ok"] is True


def test_restore_with_node_id_uses_latest_backup(
    client: FlaskClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from meshvault.backup import build_backup_payload
    from meshtastic.protobuf import localonly_pb2

    payload = build_backup_payload(
        "!a1b2c3d4", None, None, None, localonly_pb2.LocalConfig(), localonly_pb2.LocalModuleConfig()
    )
    storage.write_backup(tmp_path, "!a1b2c3d4", payload, datetime(2026, 1, 1, tzinfo=timezone.utc))

    monkeypatch.setattr(web_app.device, "open_device", _fake_open_device)
    monkeypatch.setattr(web_app.device, "restore_to_interface", lambda _interface, _data: None)

    response = client.post("/api/restore", json={"port": "COM3", "node_id": "!a1b2c3d4"})

    assert response.get_json()["ok"] is True


def test_restore_with_node_id_returns_error_when_no_backups(client: FlaskClient) -> None:
    response = client.post("/api/restore", json={"port": "COM3", "node_id": "!a1b2c3d4"})
    data = response.get_json()

    assert data["ok"] is False
    assert "!a1b2c3d4" in data["error"]


def test_restore_with_neither_uses_connected_device_node_id(
    client: FlaskClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from meshvault.backup import build_backup_payload
    from meshtastic.protobuf import localonly_pb2

    payload = build_backup_payload(
        "!a1b2c3d4", None, None, None, localonly_pb2.LocalConfig(), localonly_pb2.LocalModuleConfig()
    )
    storage.write_backup(tmp_path, "!a1b2c3d4", payload, datetime(2026, 1, 1, tzinfo=timezone.utc))

    monkeypatch.setattr(web_app.device, "open_device", _fake_open_device)
    monkeypatch.setattr(web_app.device, "get_node_id", lambda _interface: "!a1b2c3d4")
    monkeypatch.setattr(web_app.device, "restore_to_interface", lambda _interface, _data: None)

    response = client.post("/api/restore", json={"port": "COM3"})
    data = response.get_json()

    assert data["ok"] is True
    assert data["node_id"] == "!a1b2c3d4"


def test_device_backups_returns_backups_for_connected_device(
    client: FlaskClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage.write_backup(tmp_path, "!a1b2c3d4", {"node_id": "!a1b2c3d4"}, datetime(2026, 1, 1, tzinfo=timezone.utc))
    monkeypatch.setattr(web_app.device, "open_device", _fake_open_device)
    monkeypatch.setattr(web_app.device, "get_node_id", lambda _interface: "!a1b2c3d4")

    response = client.post("/api/device-backups", json={"port": "COM3"})
    data = response.get_json()

    assert data["ok"] is True
    assert data["node_id"] == "!a1b2c3d4"
    assert data["backups"] == ["backup-20260101T000000Z.json"]


def test_device_backups_returns_empty_list_when_none(
    client: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(web_app.device, "open_device", _fake_open_device)
    monkeypatch.setattr(web_app.device, "get_node_id", lambda _interface: "!a1b2c3d4")

    response = client.post("/api/device-backups", json={"port": "COM3"})

    assert response.get_json() == {"ok": True, "node_id": "!a1b2c3d4", "backups": []}


def test_export_channels_writes_plain_channel_set(
    client: FlaskClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(web_app.device, "open_device", _fake_open_device)
    monkeypatch.setattr(web_app.device, "export_channel_url", lambda _interface: "https://x")

    response = client.post("/api/export-channels", json={"port": "COM3", "name": "office"})
    data = response.get_json()

    assert data["ok"] is True
    assert storage.read_channels(tmp_path, "office") == {"channel_url": "https://x"}


def test_export_channels_writes_encrypted_channel_set(
    client: FlaskClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(web_app.device, "open_device", _fake_open_device)
    monkeypatch.setattr(web_app.device, "export_channel_url", lambda _interface: "https://x")

    response = client.post(
        "/api/export-channels",
        json={"port": "COM3", "name": "office", "encrypt": True, "password": "secret"},
    )

    assert response.get_json()["ok"] is True
    assert crypto.is_encrypted(storage.read_channels(tmp_path, "office"))


def test_export_channels_requires_password_when_encrypt_true(
    client: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        web_app.device, "open_device", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("opened device"))
    )

    response = client.post("/api/export-channels", json={"port": "COM3", "name": "office", "encrypt": True})
    data = response.get_json()

    assert data["ok"] is False
    assert "password" in data["error"].lower()


def test_import_channels_applies_plain_channel_set(
    client: FlaskClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage.write_channels(tmp_path, "office", {"channel_url": "https://x"})
    monkeypatch.setattr(web_app.device, "open_device", _fake_open_device)
    applied: list[str] = []
    monkeypatch.setattr(
        web_app.device, "import_channel_url", lambda _interface, url: applied.append(url)
    )

    response = client.post("/api/import-channels", json={"port": "COM3", "name": "office"})

    assert response.get_json()["ok"] is True
    assert applied == ["https://x"]


def test_import_channels_returns_error_when_name_not_found(client: FlaskClient) -> None:
    response = client.post("/api/import-channels", json={"port": "COM3", "name": "missing"})
    data = response.get_json()

    assert data["ok"] is False
    assert "missing" in data["error"]


def test_import_channels_needs_password_for_encrypted_set(
    client: FlaskClient, tmp_path: Path
) -> None:
    storage.write_channels(tmp_path, "secret", crypto.encrypt_payload({"channel_url": "https://x"}, "pw"))

    response = client.post("/api/import-channels", json={"port": "COM3", "name": "secret"})
    data = response.get_json()

    assert data["ok"] is False
    assert data["needs_password"] is True


def test_import_channels_wrong_password_returns_needs_password(
    client: FlaskClient, tmp_path: Path
) -> None:
    storage.write_channels(tmp_path, "secret", crypto.encrypt_payload({"channel_url": "https://x"}, "pw"))

    response = client.post(
        "/api/import-channels", json={"port": "COM3", "name": "secret", "password": "wrong"}
    )
    data = response.get_json()

    assert data["ok"] is False
    assert data["needs_password"] is True
    assert "Incorrect password" in data["error"]


def test_import_channels_correct_password_succeeds(
    client: FlaskClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    storage.write_channels(tmp_path, "secret", crypto.encrypt_payload({"channel_url": "https://x"}, "pw"))
    monkeypatch.setattr(web_app.device, "open_device", _fake_open_device)
    monkeypatch.setattr(web_app.device, "import_channel_url", lambda _interface, _url: None)

    response = client.post(
        "/api/import-channels", json={"port": "COM3", "name": "secret", "password": "pw"}
    )

    assert response.get_json()["ok"] is True


def test_post_rejected_with_foreign_origin(client: FlaskClient) -> None:
    response = client.post(
        "/api/import-channels",
        json={"port": "COM3", "name": "missing"},
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 403


def test_post_allowed_with_matching_origin(client: FlaskClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_app.device, "scan_ports", lambda: [])
    monkeypatch.setattr(
        web_app.device, "open_device", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("opened device"))
    )

    response = client.post(
        "/api/backup", json={}, headers={"Origin": "http://localhost"}
    )

    assert response.status_code != 403
