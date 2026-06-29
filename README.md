# MeshVault

A CLI (and local web GUI) for backing up and restoring [Meshtastic](https://meshtastic.org/) device configs over USB serial or Bluetooth (BLE).

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

Every command below needs the `uv run` prefix shown (e.g. `uv run meshvault-scan`) -- the `meshvault`/`meshvault-*` commands only exist inside this project's virtual environment, not on your shell's normal PATH. There are two ways to drop the prefix:

**Per-session (lasts until you close the terminal):** activate the venv.

```
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate
```

**Permanent, from any directory:** install as a uv tool in editable mode. This puts `meshvault`/`meshvault-*` on your normal PATH for good (no activation, no `cd`-ing into this repo first), while still picking up code changes immediately since `--editable` points at this source tree rather than copying it.

```
uv tool install --editable .
```

Things to know about this install:

- If you add a new *dependency* to `pyproject.toml` (not just edit existing code), rerun `uv tool install --editable .` (or `uv tool upgrade meshvault`) to pick it up. Editable mode only auto-reflects source code changes, not dependency changes.
- It's a reference to this exact folder path. If you move or rename this repo, the installed commands break until you reinstall from the new location.
- It's a separate, isolated environment from this repo's own `.venv` (managed by uv under its own tool directory, e.g. `%APPDATA%\uv\tools` on Windows) -- it won't conflict with or affect any other uv project's dependencies.
- To remove it: `uv tool uninstall meshvault`.

With either approach, every `uv run meshvault-backup ...` example below can be run as just `meshvault-backup ...`.

## Commands

Each command below is available both as a `meshvault <command>` subcommand and as a standalone `meshvault-<command>` shortcut script — the two are equivalent.

### `help` / `meshvault-help`

List all commands with a one-line description of each (same as `meshvault --help`).

```
uv run meshvault help
uv run meshvault-help
```

### `scan` / `meshvault-scan`

List serial ports with a Meshtastic device attached.

```
uv run meshvault scan
uv run meshvault-scan
```

Pass `--ble` to scan for nearby Meshtastic BLE devices instead (takes about 10 seconds):

```
uv run meshvault-scan --ble
```

### `backup` / `meshvault-backup`

Back up the config of a connected device. Writes a new timestamped backup under `working/<node-id>/`. `--port` can be omitted if exactly one Meshtastic device is connected -- see [`--port`](#--port) and [`--ble`](#--ble) below.

```
uv run meshvault backup --port COM5
uv run meshvault-backup --port COM5

# Omit --port if only one device is connected
uv run meshvault-backup

# Connect over BLE instead of serial
uv run meshvault-backup --ble

# Encrypt the backup with a password (prompted for, with confirmation)
uv run meshvault-backup --port COM5 --encrypt
```

### `restore` / `meshvault-restore`

Restore a backup onto a connected device. `--port` can be omitted if exactly one device is connected. If the backup file is encrypted, you'll be prompted for the password before it's applied.

```
# Restore the connected device's own latest backup
uv run meshvault-restore --port COM5

# Restore a specific device's latest backup (e.g. onto a replacement device)
uv run meshvault-restore --port COM5 --node-id "!a1b2c3d4"

# Restore an exact backup file
uv run meshvault-restore --port COM5 --file working/!a1b2c3d4/backup-20260624T153000Z.json

# Connect over BLE instead of serial
uv run meshvault-restore --ble
```

### `list` / `meshvault-list`

List all known devices (from the `working/` folder) and their backups -- doesn't need a device connected.

```
uv run meshvault list
uv run meshvault-list
```

### `device-backups` / `meshvault-device-backups`

List backups for one connected device: the one on `--port`, or auto-detected if exactly one device is connected. Unlike `list`, this talks to the device to find out its node id, so use it when you want "what backups exist for *this* device" rather than browsing everything in `working/`.

```
uv run meshvault device-backups --port COM5
uv run meshvault-device-backups --port COM5
uv run meshvault-device-backups
```

### `delete-backup` / `meshvault-delete-backup`

Delete one saved backup file. Doesn't need a device connected -- it just removes the file from `working/<node-id>/`.

```
uv run meshvault delete-backup "!a1b2c3d4" backup-20260624T153000Z.json
uv run meshvault-delete-backup "!a1b2c3d4" backup-20260624T153000Z.json
```

### `list-channels` / `meshvault-list-channels`

List known channel sets saved with `export-channels`, marking which ones are encrypted. Doesn't need a device connected -- it just browses `working/channels/`.

```
uv run meshvault list-channels
uv run meshvault-list-channels
```

### `export-channels` / `meshvault-export-channels`

Save a connected device's channels (and the LoRa modem config they depend on) to a named, sharable file under `working/channels/<name>.json`. `--port` can be omitted if exactly one device is connected.

```
uv run meshvault export-channels --port COM5 office
uv run meshvault-export-channels --port COM5 office

# Connect over BLE instead of serial
uv run meshvault-export-channels office --ble

# Encrypt the saved channel set with a password (prompted for, with confirmation)
uv run meshvault-export-channels --port COM5 --encrypt office
```

### `import-channels` / `meshvault-import-channels`

Apply a saved channel set to a connected device. This **overwrites** the device's existing channels by index (channel 0 becomes the saved primary, channel 1 the first saved secondary, etc.) and updates its LoRa modem config to match -- the same behavior as scanning a Meshtastic channel QR code. Any extra channel already on the device beyond the saved set's count is left alone, not disabled. `--port` can be omitted if exactly one device is connected. If the saved channel set is encrypted, you'll be prompted for the password before it's applied.

```
uv run meshvault import-channels --port COM5 office
uv run meshvault-import-channels --port COM5 office

# Connect over BLE instead of serial
uv run meshvault-import-channels office --ble
```

### `delete-channels` / `meshvault-delete-channels`

Delete a saved channel set. Doesn't need a device connected -- it just removes the file from `working/channels/`.

```
uv run meshvault delete-channels office
uv run meshvault-delete-channels office
```

### `flash-firmware` / `meshvault-flash-firmware`

Detect a connected device's hardware model, then (with confirmation) open the official [Meshtastic web flasher](https://flasher.meshtastic.org/) to update its firmware. `--port` can be omitted if exactly one device is connected.

MeshVault doesn't flash firmware itself: ESP32 boards need [esptool](https://github.com/espressif/esptool) and nRF52/RP2040 boards need a UF2 drag-and-drop bootloader, and the official web flasher already handles every board correctly via the browser's [Web Serial](https://developer.chrome.com/docs/capabilities/serial) access -- so this command identifies the device and hands off to it rather than reimplementing board-specific flashing logic.

```
uv run meshvault flash-firmware --port COM5
uv run meshvault-flash-firmware --port COM5

# Omit --port if only one device is connected
uv run meshvault-flash-firmware
```

The web flasher needs a USB connection -- it can't flash over Bluetooth -- so `--ble` only helps with detecting the hardware model here, not with the actual flash.

### `gui` / `meshvault-gui`

Start a local web GUI covering all the commands above, in your browser, instead of using the terminal.

```
uv run meshvault gui
uv run meshvault-gui
```

This prints a `http://127.0.0.1:<port>/` URL and opens it in your default browser automatically. The server only binds to `127.0.0.1` (localhost) -- it's never reachable from other devices on your network. By default an OS-assigned free port is used (a fresh one each run); pass `--http-port` to pin a specific one:

```
uv run meshvault-gui --http-port 8765
```

`--working-dir` works the same as it does for the other commands (see [`--working-dir`](#--working-dir) below), but note that `gui` doesn't take `--port`/`--ble` -- device connection (serial port or BLE) is chosen per-action inside the browser UI instead.

`gui` also starts the [`meshtastic-web`](#meshtastic-web--meshvault-meshtastic-web) client alongside it (on its fixed default port, matching the "Open Meshtastic Web Client" link shown in the page) and stops it when `gui` stops. This is best-effort: if there's no network for a first-time download, or that port's already taken by a separately-running `meshvault-meshtastic-web`, `gui` prints a warning and keeps running without it rather than failing.

### `meshtastic-web` / `meshvault-meshtastic-web`

Download (first run only) and serve the official [Meshtastic web client](https://github.com/meshtastic/web) -- the same app behind [client.meshtastic.org](https://client.meshtastic.org) -- locally in your browser, for messaging and live device management that this tool itself doesn't do.

```
uv run meshvault meshtastic-web
uv run meshvault-meshtastic-web
```

This is a separate, third-party, GPL-3.0-licensed project we don't vendor -- the command downloads a pinned release straight from its official GitHub releases at runtime (the same `build.tar` asset you could download yourself) and caches it under `<working-dir>/.meshtastic-web-client/<version>/`, so only the first run needs network access. Like `gui`, it binds to `127.0.0.1` only.

Unlike `gui`'s ephemeral port, this defaults to a **fixed** port (`8766`) so the "Open Meshtastic Web Client" link shown in `gui`'s web UI keeps working across runs:

```
uv run meshvault-meshtastic-web --http-port 9000          # use a different port
uv run meshvault-meshtastic-web --client-version v2.7.0   # pin a different release
```

If you change `--http-port` here, the "Open Meshtastic Web Client" link in `gui` (which always points at the default `8766`) will no longer match -- it only knows the default, not whatever port you actually used.

### Encrypting backups and channel sets

`backup` and `export-channels` accept `--encrypt` to password-protect the saved file. You'll be prompted for the password (and asked to confirm it) interactively -- it's never passed on the command line, so it won't end up in shell history. `restore` and `import-channels` automatically detect an encrypted file and prompt for its password before decrypting and applying it.

Encryption uses scrypt (RFC 7914 interactive parameters) to derive a key from the password and a random per-file salt, then Fernet (AES128-CBC + HMAC, from the `cryptography` package) for authenticated encryption. There's no password recovery -- if you forget it, the backup/channel set is unrecoverable.

### `--port`

`backup`, `restore`, `device-backups`, `export-channels`, `import-channels`, and `flash-firmware` (and their `meshvault-*` shortcuts) accept `--port` to pick which serial port to use. It's optional: if you omit it and exactly one Meshtastic device is connected, that device's port is used automatically. If none are connected, or more than one is, you'll get an error telling you to specify `--port` explicitly.

```
uv run meshvault-backup
# Backed up !a1b2c3d4 to working\!a1b2c3d4\backup-...json

uv run meshvault-backup
# Multiple devices detected (COM3, COM5). Specify --port to choose one.
```

### `--ble`

The same commands also accept `--ble` instead of `--port`, to connect over Bluetooth instead of USB serial -- the two are mutually exclusive. Used alone, `--ble` connects to the only nearby Meshtastic BLE device, if there's exactly one (use `meshvault-scan --ble` to see what's nearby first). Give it a value -- the device's advertised name or BLE address -- to pick a specific one when more than one is nearby:

```
uv run meshvault-backup --ble
uv run meshvault-backup --ble "Jeba 325c"
```

For `export-channels`/`import-channels`, put the channel-set name *before* `--ble` (or use `--ble=NAME`), since `--ble`'s optional value would otherwise swallow the name as its own argument:

```
uv run meshvault-export-channels office --ble
uv run meshvault-export-channels --ble=mydevice office
```

### `--working-dir`

`backup`, `restore`, `list`, `device-backups`, `delete-backup`, `list-channels`, `export-channels`, `import-channels`, `delete-channels`, `gui`, and `meshtastic-web` (and their `meshvault-*` shortcuts) accept `--working-dir` after the command/subcommand to use a folder other than `working/`. For `meshtastic-web` this only changes where the downloaded client is cached (under `<dir>/.meshtastic-web-client/`), not any backup/channel data. `scan` doesn't take it, since it doesn't touch the working dir.

```
uv run meshvault list --working-dir /path/to/backups
uv run meshvault-list --working-dir /path/to/backups
```

## Development

```
uv run pytest
uv run pyright meshvault main.py
```

`meshvault/device.py` talks directly to real hardware over serial or BLE and has no automated tests -- everything else (`storage.py`, `backup.py`, `crypto.py`, `connection.py`, `cli.py`, `web/app.py`, `meshtastic_web.py`) is covered by unit tests (the actual download from GitHub is mocked at the network boundary; everything around it -- extraction, decompression, caching, serving -- runs for real against a fake tarball). See [TESTING.md](TESTING.md) for the manual checklist to run against a real device whenever device-facing behavior changes.
