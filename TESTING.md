# Manual Test Plan

`meshprogrammer/storage.py`, `backup.py`, `crypto.py`, and the non-hardware parts of `cli.py` are covered by automated tests (`uv run pytest`). `device.py` and the hardware-touching CLI handlers are not -- they require a real Meshtastic device over USB serial. Run through this checklist against real hardware whenever device-facing behavior changes.

## Prerequisites

- [ ] At least one Meshtastic device connected via USB serial
- [ ] (Optional, for cross-device tests) a second Meshtastic device
- [ ] `uv sync` has been run
- [ ] Noted the device's serial port (e.g. `COM5`) from `scan` below

All commands below need the `uv run` prefix shown (e.g. `uv run mesh-scan`, `uv run meshprogrammer scan`) -- the `meshprogrammer`/`mesh-*` commands only exist inside this project's virtual environment, so a bare `scan` or `backup --port COM5` typed directly in your shell will fail with a "not recognized" error. If you'd rather not type `uv run` every time, activate the venv first and drop the prefix for the rest of the session:

```
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate
```

## help / mesh-help

- [ ] `uv run meshprogrammer help` lists every command (help, scan, backup, restore, list, device-backups, export-channels, import-channels) with a one-line description
- [ ] `uv run mesh-help` produces the same output
- [ ] Output matches `uv run meshprogrammer --help`
- [ ] Output mentions `--port` and `--encrypt` and which commands accept them

## scan / mesh-scan

- [ ] `uv run meshprogrammer scan` lists the connected device's port
- [ ] `uv run mesh-scan` produces the same result
- [ ] Unplug the device; `uv run mesh-scan` reports "No Meshtastic devices detected."
- [ ] `uv run mesh-scan --working-dir /tmp` is rejected (scan doesn't accept this flag)

## backup / mesh-backup

`--port` is optional throughout: if omitted and exactly one Meshtastic device is connected, its port is used automatically.

- [ ] `uv run mesh-backup [--port <PORT>]` succeeds, printing the node id and backup path
- [ ] The backup file exists at `working/<node-id>/backup-<timestamp>.json`
- [ ] The backup file contains `local_config`, `module_config`, owner name, and `channel_url`
- [ ] Running it twice creates two distinct timestamped files (not an overwrite)
- [ ] `uv run meshprogrammer backup [--port <PORT>]` produces the same result as `mesh-backup`
- [ ] `uv run mesh-backup [--port <PORT>] --working-dir <DIR>` writes under `<DIR>/<node-id>/` instead of `working/`
- [ ] `uv run mesh-backup --port <bad-port>` fails with a clear error, not a crash

## backup --encrypt

- [ ] `uv run mesh-backup [--port <PORT>] --encrypt` prompts for a password and a confirmation
- [ ] A mismatched confirmation re-prompts with "Passwords did not match, try again."
- [ ] An empty password is rejected and re-prompted
- [ ] The resulting file is named `encryptedbackup-<timestamp>.json`, not `backup-<timestamp>.json`
- [ ] The resulting backup file has `"encrypted": true` and no readable plaintext config
- [ ] The success message includes "(encrypted)"
- [ ] With both encrypted and plain backups present for a device, `uv run mesh-list` and `restore`'s "latest backup" pick the actual newest one regardless of which prefix it has

## restore / mesh-restore

`--port` is optional throughout: if omitted and exactly one Meshtastic device is connected, its port is used automatically.

- [ ] `uv run mesh-restore [--port <PORT>]` (no other flags) restores the connected device's own latest backup
- [ ] `uv run mesh-restore [--port <PORT>] --node-id <ID>` restores a specific device's latest backup
- [ ] `uv run mesh-restore [--port <PORT>] --file <path>` restores an exact backup file
- [ ] `--file` and `--node-id` together are rejected (mutually exclusive)
- [ ] Restoring with no backups present for a node id prints "No backups found..." and exits non-zero
- [ ] After restoring, a fresh `uv run mesh-backup [--port <PORT>]` shows the config matches what was restored
- [ ] `uv run meshprogrammer restore [--port <PORT>]` produces the same result as `mesh-restore`

## restore (encrypted backups)

- [ ] Restoring an encrypted backup prompts for "Password: "
- [ ] The correct password decrypts and restores successfully
- [ ] A wrong password prints "Incorrect password." and exits non-zero, device untouched

## list / mesh-list

- [ ] `uv run mesh-list` with no backups present prints "No backups found in ..."
- [ ] `uv run mesh-list` after one or more backups shows device id(s), backup count(s), and filenames
- [ ] `uv run meshprogrammer list` produces the same output as `mesh-list`
- [ ] `uv run mesh-list --working-dir <DIR>` lists backups from that folder instead of `working/`

## device-backups / mesh-device-backups

`--port` is optional throughout: if omitted and exactly one Meshtastic device is connected, its port is used automatically.

- [ ] `uv run mesh-device-backups [--port <PORT>]` lists only the connected device's own backups, not other devices' from `working/`
- [ ] With no backups for the connected device, prints "No backups found for <node-id> in working"
- [ ] `uv run meshprogrammer device-backups [--port <PORT>]` produces the same result as `mesh-device-backups`
- [ ] `uv run mesh-device-backups [--port <PORT>] --working-dir <DIR>` lists backups from that folder instead of `working/`
- [ ] With no device connected, prints "No Meshtastic devices detected. Specify --port." and exits non-zero
- [ ] (If you have a second device) with two devices connected and no `--port`, prints "Multiple devices detected (...). Specify --port to choose one." and exits non-zero

## export-channels / mesh-export-channels

`--port` is optional throughout: if omitted and exactly one Meshtastic device is connected, its port is used automatically.

- [ ] `uv run mesh-export-channels [--port <PORT>] <name>` succeeds, writes `working/channels/<name>.json`
- [ ] Re-running with the same name overwrites the file
- [ ] `uv run meshprogrammer export-channels [--port <PORT>] <name>` produces the same result
- [ ] `uv run mesh-export-channels [--port <PORT>] --working-dir <DIR> <name>` writes under `<DIR>/channels/`

## export-channels --encrypt

- [ ] `uv run mesh-export-channels [--port <PORT>] --encrypt <name>` prompts for password + confirmation
- [ ] The resulting file has `"encrypted": true` and no readable plaintext `channel_url`
- [ ] The success message includes "(encrypted)"

## import-channels / mesh-import-channels

`--port` is optional throughout: if omitted and exactly one Meshtastic device is connected, its port is used automatically.

- [ ] `uv run mesh-import-channels [--port <PORT>] <name>` applies the saved channel set
- [ ] After importing, exporting again from the same device shows matching channel settings (psk, name, uplink/downlink, position precision) -- LoRa modem fields (bandwidth/spreadFactor/codingRate) may now be explicit where they weren't before; that's expected firmware behavior, not a bug
- [ ] Importing a name that doesn't exist prints "No saved channel set named '<name>' ..." and exits non-zero
- [ ] (If you have a second device) export from device A, then import onto device B -- B's channels now match A's
- [ ] `uv run meshprogrammer import-channels [--port <PORT>] <name>` produces the same result as `mesh-import-channels`

## import-channels (encrypted)

- [ ] Importing an encrypted channel set prompts for "Password: "
- [ ] The correct password decrypts and applies successfully
- [ ] A wrong password prints "Incorrect password." and exits non-zero, device untouched

## --port auto-detection edge cases

- [ ] With no device connected, `uv run mesh-backup` (no `--port`) prints "No Meshtastic devices detected. Specify --port." and exits non-zero
- [ ] (If you have a second device) with two devices connected, `uv run mesh-backup` (no `--port`) prints "Multiple devices detected (<PORT1>, <PORT2>). Specify --port to choose one." and exits non-zero
- [ ] In both cases above, no backup file is written and the device(s) are untouched
- [ ] The same no-device/multiple-device behavior holds for `mesh-restore`, `mesh-device-backups`, `mesh-export-channels`, and `mesh-import-channels`

## General

- [ ] `uv run meshprogrammer --help` and each `meshprogrammer <command> --help` show accurate, current usage
- [ ] `uv run pytest` passes
- [ ] `uv run pyright meshprogrammer main.py` reports 0 errors
