import gzip
import io
import tarfile
from pathlib import Path

import pytest

from meshvault import meshtastic_web


def _write_fake_release_tar(dest: Path, files: dict[str, bytes]) -> None:
    """Write a tar at ``dest`` with each entry gzip-compressed, matching the
    real meshtastic/web release's layout (every file shipped as ``<name>.gz``,
    even index.html, for a server that does on-the-fly gzip negotiation)."""
    with tarfile.open(dest, "w") as tar:
        for name, content in files.items():
            compressed = gzip.compress(content)
            info = tarfile.TarInfo(name=f"{name}.gz")
            info.size = len(compressed)
            tar.addfile(info, io.BytesIO(compressed))


def test_release_url_uses_version_in_path() -> None:
    assert meshtastic_web._release_url("v2.7.1") == (
        "https://github.com/meshtastic/web/releases/download/v2.7.1/build.tar"
    )


def test_ensure_client_downloaded_extracts_and_decompresses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fake_download(_url: str, dest: Path) -> None:
        _write_fake_release_tar(
            dest, {"index.html": b"<html>hello</html>", "assets/app.js": b"console.log('hi')"}
        )

    monkeypatch.setattr(meshtastic_web, "_download_release_tar", _fake_download)

    client_dir = meshtastic_web.ensure_client_downloaded(tmp_path, "v9.9.9")

    assert (client_dir / "index.html").read_bytes() == b"<html>hello</html>"
    assert (client_dir / "assets" / "app.js").read_bytes() == b"console.log('hi')"
    assert not list(client_dir.rglob("*.gz"))


def test_ensure_client_downloaded_uses_cache_on_second_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def _fake_download(url: str, dest: Path) -> None:
        calls.append(url)
        _write_fake_release_tar(dest, {"index.html": b"cached"})

    monkeypatch.setattr(meshtastic_web, "_download_release_tar", _fake_download)

    first = meshtastic_web.ensure_client_downloaded(tmp_path, "v9.9.9")
    second = meshtastic_web.ensure_client_downloaded(tmp_path, "v9.9.9")

    assert first == second
    assert len(calls) == 1


def test_ensure_client_downloaded_caches_separately_per_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fake_download(url: str, dest: Path) -> None:
        version = url.rsplit("/", 2)[-2]
        _write_fake_release_tar(dest, {"index.html": version.encode()})

    monkeypatch.setattr(meshtastic_web, "_download_release_tar", _fake_download)

    dir_a = meshtastic_web.ensure_client_downloaded(tmp_path, "v1.0.0")
    dir_b = meshtastic_web.ensure_client_downloaded(tmp_path, "v2.0.0")

    assert dir_a != dir_b
    assert (dir_a / "index.html").read_bytes() == b"v1.0.0"
    assert (dir_b / "index.html").read_bytes() == b"v2.0.0"


def test_download_release_tar_wraps_url_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import urllib.error

    def _fake_urlretrieve(_url: str, _dest: Path) -> None:
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(meshtastic_web.urllib.request, "urlretrieve", _fake_urlretrieve)

    with pytest.raises(RuntimeError, match="Failed to download"):
        meshtastic_web._download_release_tar("https://example.invalid/build.tar", tmp_path / "build.tar")


def test_create_static_app_serves_files_with_relative_client_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test: send_from_directory resolves a relative directory
    against the Flask app's root_path (this package's folder), not the
    process's cwd. A relative client_dir -- like the real default,
    "working/.meshtastic-web-client/<version>" -- 404ed against the wrong
    location entirely until create_static_app started resolving it."""
    client_dir = tmp_path / "client"
    client_dir.mkdir()
    (client_dir / "index.html").write_text("<html>relative path test</html>")

    monkeypatch.chdir(tmp_path)
    relative_client_dir = Path("client")

    app = meshtastic_web.create_static_app(relative_client_dir)
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert response.data == b"<html>relative path test</html>"


def test_create_static_app_serves_real_files(tmp_path: Path) -> None:
    client_dir = tmp_path / "client"
    client_dir.mkdir()
    (client_dir / "index.html").write_text("<html>index</html>")
    (client_dir / "app.js").write_text("console.log('hi')")

    app = meshtastic_web.create_static_app(client_dir)
    test_client = app.test_client()

    assert test_client.get("/").data == b"<html>index</html>"
    assert test_client.get("/app.js").data == b"console.log('hi')"


def test_create_static_app_falls_back_to_index_for_spa_routes(tmp_path: Path) -> None:
    client_dir = tmp_path / "client"
    client_dir.mkdir()
    (client_dir / "index.html").write_text("<html>spa shell</html>")

    app = meshtastic_web.create_static_app(client_dir)
    test_client = app.test_client()

    response = test_client.get("/messages/broadcast/0")

    assert response.status_code == 200
    assert response.data == b"<html>spa shell</html>"
