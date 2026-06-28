"""Flask app exposing meshprogrammer's commands as a local browser GUI.

Routes are a 1:1 JSON-API mirror of the ``run_*`` command functions in
``cli.py``, reusing the same ``device``/``storage``/``crypto``/``backup``/
``connection`` modules directly rather than shelling out to the CLI. The
only behavioral difference from the CLI is how passwords are supplied:
the CLI prompts interactively via ``getpass``, while routes that need a
password for an encrypted payload take it as a JSON field and report
``needs_password`` in the response so the browser can prompt and retry.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from flask import Flask, Response, abort, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from meshprogrammer import backup as backup_module
from meshprogrammer import connection, crypto, device, meshtastic_web, storage


def _ok(**data: Any) -> Response:
    return jsonify({"ok": True, **data})


def _error(message: str, status: int = 400, **extra: Any) -> tuple[Response, int]:
    return jsonify({"ok": False, "error": message, **extra}), status


class _PasswordNeededError(Exception):
    """Raised by ``_decrypt_payload_if_needed`` when a password is missing or wrong."""


def _decrypt_payload_if_needed(data: dict[str, Any], password: str | None) -> dict[str, Any]:
    """Return ``data`` as-is if it's plain, or decrypted if ``password`` works.

    Raises ``_PasswordNeededError`` (with a message fit to show the user) if
    the payload is encrypted and ``password`` is missing or wrong.
    """
    if not crypto.is_encrypted(data):
        return data
    if not password:
        raise _PasswordNeededError("Password is required.")
    try:
        return crypto.decrypt_payload(data, password)
    except crypto.WrongPasswordError:
        raise _PasswordNeededError("Incorrect password.") from None


def _resolve_restore_target(
    working_dir: Path, node_id: str | None, filename: str | None
) -> tuple[Path | None, str | None]:
    """Return ``(path, error)``. ``(None, None)`` means: discover via the connected device."""
    if filename is not None:
        if node_id is None:
            return None, "node_id is required when filename is given."
        for backup_file in storage.list_backups(working_dir, node_id):
            if backup_file.name == filename:
                return backup_file, None
        return None, f"No such backup '{filename}' for {node_id}."
    if node_id is not None:
        path = storage.latest_backup(working_dir, node_id)
        if path is None:
            return None, f"No backups found for {node_id}."
        return path, None
    return None, None


def create_app(working_dir: Path) -> Flask:
    app = Flask(__name__)

    @app.errorhandler(HTTPException)
    def _pass_through_http_exception(exc: HTTPException):
        return exc

    @app.errorhandler(Exception)
    def _handle_unexpected_error(exc: Exception):
        return _error(str(exc), status=500)

    @app.before_request
    def _reject_cross_origin_writes() -> None:
        if request.method == "GET":
            return
        origin = request.headers.get("Origin")
        if origin is not None and urlsplit(origin).netloc != request.host:
            abort(403)

    @app.route("/")
    def index():
        meshtastic_web_url = f"http://127.0.0.1:{meshtastic_web.DEFAULT_PORT}/"
        return render_template("index.html", meshtastic_web_url=meshtastic_web_url)

    @app.route("/api/scan")
    def scan():
        if request.args.get("ble"):
            return _ok(ble_devices=device.scan_ble())
        return _ok(ports=device.scan_ports())

    @app.route("/api/list")
    def list_backups_route():
        devices = [
            {
                "node_id": node_id,
                "backups": [p.name for p in storage.list_backups(working_dir, node_id)],
            }
            for node_id in storage.list_device_ids(working_dir)
        ]
        return _ok(devices=devices)

    @app.route("/api/list-channels")
    def list_channels_route():
        channel_sets = [
            {
                "name": name,
                "encrypted": crypto.is_encrypted(storage.read_channels(working_dir, name)),
            }
            for name in storage.list_channel_names(working_dir)
        ]
        return _ok(channel_sets=channel_sets)

    @app.route("/api/backup", methods=["POST"])
    def backup():
        body = request.get_json() or {}
        port: str | None = body.get("port")
        ble: str | None = body.get("ble")
        encrypt = bool(body.get("encrypt"))
        password: str | None = body.get("password")

        if encrypt and not password:
            return _error("Password is required to encrypt.")
        if ble is None:
            try:
                port = connection.resolve_port(port)
            except connection.PortResolutionError as exc:
                return _error(str(exc))

        with device.open_device(port, ble) as interface:
            payload = device.backup_from_interface(interface)
        node_id = payload["node_id"]
        if encrypt:
            assert password is not None  # guaranteed by the encrypt/password guard above
            payload = crypto.encrypt_payload(payload, password)
        path = storage.write_backup(working_dir, node_id, payload, datetime.now(timezone.utc))
        return _ok(node_id=node_id, path=str(path), encrypted=encrypt)

    @app.route("/api/restore", methods=["POST"])
    def restore():
        body = request.get_json() or {}
        port: str | None = body.get("port")
        ble: str | None = body.get("ble")
        node_id: str | None = body.get("node_id")
        filename: str | None = body.get("filename")
        password: str | None = body.get("password")

        target, target_error = _resolve_restore_target(working_dir, node_id, filename)
        if target_error is not None:
            return _error(target_error)

        if ble is None:
            try:
                port = connection.resolve_port(port)
            except connection.PortResolutionError as exc:
                return _error(str(exc))

        if target is not None:
            try:
                data = _decrypt_payload_if_needed(storage.read_backup(target), password)
            except _PasswordNeededError as exc:
                return _error(str(exc), needs_password=True)
            parsed = backup_module.parse_backup_payload(data)
            with device.open_device(port, ble) as interface:
                device.restore_to_interface(interface, parsed)
            return _ok(path=str(target))

        with device.open_device(port, ble) as interface:
            own_node_id = device.get_node_id(interface)
            backup_path = storage.latest_backup(working_dir, own_node_id)
            if backup_path is None:
                return _error(f"No backups found for {own_node_id}.")
            try:
                data = _decrypt_payload_if_needed(storage.read_backup(backup_path), password)
            except _PasswordNeededError as exc:
                return _error(str(exc), needs_password=True, node_id=own_node_id)
            parsed = backup_module.parse_backup_payload(data)
            device.restore_to_interface(interface, parsed)
        return _ok(path=str(backup_path), node_id=own_node_id)

    @app.route("/api/device-backups", methods=["POST"])
    def device_backups():
        body = request.get_json() or {}
        port = body.get("port")
        ble = body.get("ble")

        if ble is None:
            try:
                port = connection.resolve_port(port)
            except connection.PortResolutionError as exc:
                return _error(str(exc))

        with device.open_device(port, ble) as interface:
            node_id = device.get_node_id(interface)
        backups = storage.list_backups(working_dir, node_id)
        return _ok(node_id=node_id, backups=[p.name for p in backups])

    @app.route("/api/export-channels", methods=["POST"])
    def export_channels():
        body = request.get_json() or {}
        port: str | None = body.get("port")
        ble: str | None = body.get("ble")
        name: str | None = body.get("name")
        encrypt = bool(body.get("encrypt"))
        password: str | None = body.get("password")

        if not name:
            return _error("A name is required.")
        if encrypt and not password:
            return _error("Password is required to encrypt.")
        if ble is None:
            try:
                port = connection.resolve_port(port)
            except connection.PortResolutionError as exc:
                return _error(str(exc))

        with device.open_device(port, ble) as interface:
            channel_url = device.export_channel_url(interface)
        payload: dict[str, Any] = {"channel_url": channel_url}
        if encrypt:
            assert password is not None  # guaranteed by the encrypt/password guard above
            payload = crypto.encrypt_payload(payload, password)
        path = storage.write_channels(working_dir, name, payload)
        return _ok(path=str(path), encrypted=encrypt)

    @app.route("/api/import-channels", methods=["POST"])
    def import_channels():
        body = request.get_json() or {}
        port: str | None = body.get("port")
        ble: str | None = body.get("ble")
        name: str | None = body.get("name")
        password: str | None = body.get("password")

        if not name:
            return _error("A name is required.")

        try:
            data = storage.read_channels(working_dir, name)
        except FileNotFoundError:
            return _error(f"No saved channel set named '{name}'.")

        try:
            decrypted = _decrypt_payload_if_needed(data, password)
        except _PasswordNeededError as exc:
            return _error(str(exc), needs_password=True)
        if ble is None:
            try:
                port = connection.resolve_port(port)
            except connection.PortResolutionError as exc:
                return _error(str(exc))

        with device.open_device(port, ble) as interface:
            device.import_channel_url(interface, decrypted["channel_url"])
        return _ok()

    return app
