# meshprogrammer

A CLI for backing up and restoring [Meshtastic](https://meshtastic.org/) device configs over USB serial.

Backups are stored under a `working/` folder in the repo root, one subfolder per device named by the device's own node id (e.g. `!a1b2c3d4`), with one timestamped JSON file per backup: `backup-<timestamp>.json`, or `encryptedbackup-<timestamp>.json` if it was saved with `--encrypt`. Shared channel sets (see `export-channels`/`import-channels` below) live under `working/channels/`, one named file each. `working/` is gitignored because backups and channel sets can contain device private/admin keys and channel encryption keys.

## Setup

This project uses [uv](https://docs.astral.sh/uv/) for Python package and script management. If you don't have it installed:

```
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

See the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/) for other options (pipx, Homebrew, etc.).

Then install this project's dependencies:

```
uv sync
```

Every command below needs the `uv run` prefix shown (e.g. `uv run mesh-scan`) -- the `meshprogrammer`/`mesh-*` commands only exist inside this project's virtual environment, not on your shell's normal PATH. There are two ways to drop the prefix:

**Per-session (lasts until you close the terminal):** activate the venv.

```
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate
```

**Permanent, from any directory:** install as a uv tool in editable mode. This puts `meshprogrammer`/`mesh-*` on your normal PATH for good (no activation, no `cd`-ing into this repo first), while still picking up code changes immediately since `--editable` points at this source tree rather than copying it.

```
uv tool install --editable .
```

Things to know about this install:

- If you add a new *dependency* to `pyproject.toml` (not just edit existing code), rerun `uv tool install --editable .` (or `uv tool upgrade meshprogrammer`) to pick it up. Editable mode only auto-reflects source code changes, not dependency changes.
- It's a reference to this exact folder path. If you move or rename this repo, the installed commands break until you reinstall from the new location.
- It's a separate, isolated environment from this repo's own `.venv` (managed by uv under its own tool directory, e.g. `%APPDATA%\uv\tools` on Windows) -- it won't conflict with or affect any other uv project's dependencies.
- To remove it: `uv tool uninstall meshprogrammer`.

With either approach, every `uv run mesh-backup ...` example below can be run as just `mesh-backup ...`.

## Commands

Each command below is available both as a `meshprogrammer <command>` subcommand and as a standalone `mesh-<command>` shortcut script — the two are equivalent.

### `help` / `mesh-help`

List all commands with a one-line description of each (same as `meshprogrammer --help`).

```
uv run meshprogrammer help
uv run mesh-help
```

### `scan` / `mesh-scan`

List serial ports with a Meshtastic device attached.

```
uv run meshprogrammer scan
uv run mesh-scan
```

### `backup` / `mesh-backup`

Back up the config of a connected device. Writes a new timestamped backup under `working/<node-id>/`. `--port` can be omitted if exactly one Meshtastic device is connected -- see [`--port`](#--port) below.

```
uv run meshprogrammer backup --port COM5
uv run mesh-backup --port COM5

# Omit --port if only one device is connected
uv run mesh-backup

# Encrypt the backup with a password (prompted for, with confirmation)
uv run mesh-backup --port COM5 --encrypt
```

### `restore` / `mesh-restore`

Restore a backup onto a connected device. `--port` can be omitted if exactly one device is connected. If the backup file is encrypted, you'll be prompted for the password before it's applied.

```
# Restore the connected device's own latest backup
uv run mesh-restore --port COM5

# Restore a specific device's latest backup (e.g. onto a replacement device)
uv run mesh-restore --port COM5 --node-id "!a1b2c3d4"

# Restore an exact backup file
uv run mesh-restore --port COM5 --file working/!a1b2c3d4/backup-20260624T153000Z.json
```

### `list` / `mesh-list`

List all known devices (from the `working/` folder) and their backups -- doesn't need a device connected.

```
uv run meshprogrammer list
uv run mesh-list
```

### `device-backups` / `mesh-device-backups`

List backups for one connected device: the one on `--port`, or auto-detected if exactly one device is connected. Unlike `list`, this talks to the device to find out its node id, so use it when you want "what backups exist for *this* device" rather than browsing everything in `working/`.

```
uv run meshprogrammer device-backups --port COM5
uv run mesh-device-backups --port COM5
uv run mesh-device-backups
```

### `list-channels` / `mesh-list-channels`

List known channel sets saved with `export-channels`, marking which ones are encrypted. Doesn't need a device connected -- it just browses `working/channels/`.

```
uv run meshprogrammer list-channels
uv run mesh-list-channels
```

### `export-channels` / `mesh-export-channels`

Save a connected device's channels (and the LoRa modem config they depend on) to a named, sharable file under `working/channels/<name>.json`. `--port` can be omitted if exactly one device is connected.

```
uv run meshprogrammer export-channels --port COM5 office
uv run mesh-export-channels --port COM5 office

# Encrypt the saved channel set with a password (prompted for, with confirmation)
uv run mesh-export-channels --port COM5 --encrypt office
```

### `import-channels` / `mesh-import-channels`

Apply a saved channel set to a connected device. This **overwrites** the device's existing channels by index (channel 0 becomes the saved primary, channel 1 the first saved secondary, etc.) and updates its LoRa modem config to match -- the same behavior as scanning a Meshtastic channel QR code. Any extra channel already on the device beyond the saved set's count is left alone, not disabled. `--port` can be omitted if exactly one device is connected. If the saved channel set is encrypted, you'll be prompted for the password before it's applied.

```
uv run meshprogrammer import-channels --port COM5 office
uv run mesh-import-channels --port COM5 office
```

### Encrypting backups and channel sets

`backup` and `export-channels` accept `--encrypt` to password-protect the saved file. You'll be prompted for the password (and asked to confirm it) interactively -- it's never passed on the command line, so it won't end up in shell history. `restore` and `import-channels` automatically detect an encrypted file and prompt for its password before decrypting and applying it.

Encryption uses scrypt (RFC 7914 interactive parameters) to derive a key from the password and a random per-file salt, then Fernet (AES128-CBC + HMAC, from the `cryptography` package) for authenticated encryption. There's no password recovery -- if you forget it, the backup/channel set is unrecoverable.

### `--port`

`backup`, `restore`, `device-backups`, `export-channels`, and `import-channels` (and their `mesh-*` shortcuts) accept `--port` to pick which serial port to use. It's optional: if you omit it and exactly one Meshtastic device is connected, that device's port is used automatically. If none are connected, or more than one is, you'll get an error telling you to specify `--port` explicitly.

```
uv run mesh-backup
# Backed up !a1b2c3d4 to working\!a1b2c3d4\backup-...json

uv run mesh-backup
# Multiple devices detected (COM3, COM5). Specify --port to choose one.
```

### `--working-dir`

`backup`, `restore`, `list`, `device-backups`, `list-channels`, `export-channels`, and `import-channels` (and their `mesh-*` shortcuts) accept `--working-dir` after the command/subcommand to use a folder other than `working/`. `scan` doesn't take it, since it doesn't touch the working dir.

```
uv run meshprogrammer list --working-dir /path/to/backups
uv run mesh-list --working-dir /path/to/backups
```

## Development

```
uv run pytest
uv run pyright meshprogrammer main.py
```

`meshprogrammer/device.py` talks directly to real hardware over serial and has no automated tests -- everything else (`storage.py`, `backup.py`, `crypto.py`, `cli.py`) is covered by unit tests. See [TESTING.md](TESTING.md) for the manual checklist to run against a real device whenever device-facing behavior changes.
