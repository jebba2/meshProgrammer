"""Download, cache, and serve the official Meshtastic web client locally.

The client (https://github.com/meshtastic/web, the source behind
client.meshtastic.org) is a separate GPL-3.0 project we don't vendor --
this module downloads a pinned release's pre-built tarball straight from
GitHub at runtime and serves it from a local cache, the same thing a user
could do by hand. Every file in that tarball ships gzip-only (even
index.html), for a server that does on-the-fly gzip negotiation; we don't
have that, so it's decompressed once on extraction instead.
"""

import gzip
import shutil
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

from flask import Flask, send_from_directory

DEFAULT_VERSION = "v2.7.1"
DEFAULT_PORT = 8766


def _release_url(version: str) -> str:
    return f"https://github.com/meshtastic/web/releases/download/{version}/build.tar"


def _client_dir(working_dir: Path, version: str) -> Path:
    return working_dir / ".meshtastic-web-client" / version


def _download_release_tar(url: str, dest: Path) -> None:
    try:
        urllib.request.urlretrieve(url, dest)
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to download {url}: {exc}") from exc


def _decompress_in_place(extracted_dir: Path) -> None:
    for compressed_path in extracted_dir.rglob("*.gz"):
        with gzip.open(compressed_path, "rb") as src, compressed_path.with_suffix("").open("wb") as dst:
            shutil.copyfileobj(src, dst)
        compressed_path.unlink()


def ensure_client_downloaded(working_dir: Path, version: str = DEFAULT_VERSION) -> Path:
    """Return the local directory serving the meshtastic-web client at ``version``.

    Downloads and decompresses the official release tarball into a cache
    under ``working_dir`` the first time it's needed; later calls (for the
    same version) reuse the cached copy without hitting the network.
    """
    client_dir = _client_dir(working_dir, version)
    if (client_dir / "index.html").is_file():
        return client_dir

    staging_dir = client_dir.with_name(client_dir.name + ".download")
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)

    tar_path = staging_dir / "build.tar"
    _download_release_tar(_release_url(version), tar_path)

    extracted_dir = staging_dir / "extracted"
    with tarfile.open(tar_path) as tar:
        tar.extractall(extracted_dir, filter="data")
    tar_path.unlink()

    _decompress_in_place(extracted_dir)

    client_dir.parent.mkdir(parents=True, exist_ok=True)
    extracted_dir.replace(client_dir)
    shutil.rmtree(staging_dir, ignore_errors=True)
    return client_dir


def create_static_app(client_dir: Path) -> Flask:
    """Serve ``client_dir`` as a single-page app: real files as-is, any
    other path (e.g. a client-side route like /messages/broadcast/0)
    falls back to index.html."""
    # send_from_directory resolves a relative directory against the Flask
    # app's root_path (this module's folder), not the process's cwd -- so a
    # relative client_dir (e.g. the default "working/...") would 404 against
    # the wrong location entirely. Resolve to absolute to sidestep that.
    client_dir = client_dir.resolve()
    app = Flask(__name__)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve(path: str):
        if path and (client_dir / path).is_file():
            return send_from_directory(client_dir, path)
        return send_from_directory(client_dir, "index.html")

    return app
