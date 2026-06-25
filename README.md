# meshprogrammer

A CLI for backing up and restoring [Meshtastic](https://meshtastic.org/) device configs over USB serial.

Backups are stored under a `working/` folder in the repo root, one subfolder per device named by the device's own node id (e.g. `!a1b2c3d4`), with one timestamped JSON file per backup. `working/` is gitignored because backups can contain device private/admin keys.

## Setup

```
uv sync
```

## Commands

### `scan`

List serial ports with a Meshtastic device attached.

```
uv run meshprogrammer scan
```

### `backup`

Back up the config of the device connected on a given serial port. Writes a new timestamped backup under `working/<node-id>/`.

```
uv run meshprogrammer backup --port COM5
```

### `restore`

Restore a backup onto the device connected on a given serial port.

```
# Restore the connected device's own latest backup
uv run meshprogrammer restore --port COM5

# Restore a specific device's latest backup (e.g. onto a replacement device)
uv run meshprogrammer restore --port COM5 --node-id "!a1b2c3d4"

# Restore an exact backup file
uv run meshprogrammer restore --port COM5 --file working/!a1b2c3d4/backup-20260624T153000Z.json
```

### `list`

List known devices and their backups.

```
uv run meshprogrammer list
```

### `--working-dir`

All commands accept `--working-dir` to use a folder other than `working/`:

```
uv run meshprogrammer --working-dir /path/to/backups list
```

## Development

```
uv run pytest
uv run pyright meshprogrammer main.py
```

`meshprogrammer/device.py` talks directly to real hardware over serial and has no automated tests — it's verified manually against a real device. Everything else (`storage.py`, `backup.py`, `cli.py`) is covered by unit tests.
