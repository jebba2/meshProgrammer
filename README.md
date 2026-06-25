# meshprogrammer

A CLI for backing up and restoring [Meshtastic](https://meshtastic.org/) device configs over USB serial.

Backups are stored under a `working/` folder in the repo root, one subfolder per device named by the device's own node id (e.g. `!a1b2c3d4`), with one timestamped JSON file per backup. Shared channel sets (see `export-channels`/`import-channels` below) live under `working/channels/`, one named file each. `working/` is gitignored because backups and channel sets can contain device private/admin keys and channel encryption keys.

## Setup

```
uv sync
```

## Commands

Each command below is available both as a `meshprogrammer <command>` subcommand and as a standalone `mesh-<command>` shortcut script — the two are equivalent.

### `scan` / `mesh-scan`

List serial ports with a Meshtastic device attached.

```
uv run meshprogrammer scan
uv run mesh-scan
```

### `backup` / `mesh-backup`

Back up the config of the device connected on a given serial port. Writes a new timestamped backup under `working/<node-id>/`.

```
uv run meshprogrammer backup --port COM5
uv run mesh-backup --port COM5

# Encrypt the backup with a password (prompted for, with confirmation)
uv run mesh-backup --port COM5 --encrypt
```

### `restore` / `mesh-restore`

Restore a backup onto the device connected on a given serial port. If the backup file is encrypted, you'll be prompted for the password before it's applied.

```
# Restore the connected device's own latest backup
uv run mesh-restore --port COM5

# Restore a specific device's latest backup (e.g. onto a replacement device)
uv run mesh-restore --port COM5 --node-id "!a1b2c3d4"

# Restore an exact backup file
uv run mesh-restore --port COM5 --file working/!a1b2c3d4/backup-20260624T153000Z.json
```

### `list` / `mesh-list`

List known devices and their backups.

```
uv run meshprogrammer list
uv run mesh-list
```

### `export-channels` / `mesh-export-channels`

Save a connected device's channels (and the LoRa modem config they depend on) to a named, sharable file under `working/channels/<name>.json`.

```
uv run meshprogrammer export-channels --port COM5 office
uv run mesh-export-channels --port COM5 office

# Encrypt the saved channel set with a password (prompted for, with confirmation)
uv run mesh-export-channels --port COM5 --encrypt office
```

### `import-channels` / `mesh-import-channels`

Apply a saved channel set to a connected device. This **overwrites** the device's existing channels by index (channel 0 becomes the saved primary, channel 1 the first saved secondary, etc.) and updates its LoRa modem config to match -- the same behavior as scanning a Meshtastic channel QR code. Any extra channel already on the device beyond the saved set's count is left alone, not disabled. If the saved channel set is encrypted, you'll be prompted for the password before it's applied.

```
uv run meshprogrammer import-channels --port COM5 office
uv run mesh-import-channels --port COM5 office
```

### Encrypting backups and channel sets

`backup` and `export-channels` accept `--encrypt` to password-protect the saved file. You'll be prompted for the password (and asked to confirm it) interactively -- it's never passed on the command line, so it won't end up in shell history. `restore` and `import-channels` automatically detect an encrypted file and prompt for its password before decrypting and applying it.

Encryption uses scrypt (RFC 7914 interactive parameters) to derive a key from the password and a random per-file salt, then Fernet (AES128-CBC + HMAC, from the `cryptography` package) for authenticated encryption. There's no password recovery -- if you forget it, the backup/channel set is unrecoverable.

### `--working-dir`

`backup`, `restore`, and `list` (and their `mesh-*` shortcuts) accept `--working-dir` after the command/subcommand to use a folder other than `working/`. `scan` doesn't take it, since it doesn't touch the working dir.

```
uv run meshprogrammer list --working-dir /path/to/backups
uv run mesh-list --working-dir /path/to/backups
```

## Development

```
uv run pytest
uv run pyright meshprogrammer main.py
```

`meshprogrammer/device.py` talks directly to real hardware over serial and has no automated tests — it's verified manually against a real device. Everything else (`storage.py`, `backup.py`, `cli.py`) is covered by unit tests.
