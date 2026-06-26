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

## scan / mesh-scan

- [ ] `uv run meshprogrammer scan` lists the connected device's port
- [ ] `uv run mesh-scan` produces the same result
- [ ] Unplug the device; `scan` reports "No Meshtastic devices detected."
- [ ] `scan --working-dir ...` is rejected (scan doesn't accept this flag)

## backup / mesh-backup

- [ ] `backup --port <PORT>` succeeds, printing the node id and backup path
- [ ] The backup file exists at `working/<node-id>/backup-<timestamp>.json`
- [ ] The backup file contains `local_config`, `module_config`, owner name, and `channel_url`
- [ ] Running backup twice creates two distinct timestamped files (not an overwrite)
- [ ] `mesh-backup --port <PORT>` produces the same result as `meshprogrammer backup`
- [ ] `backup --port <PORT> --working-dir <DIR>` writes under `<DIR>/<node-id>/` instead of `working/`
- [ ] `backup --port <bad-port>` fails with a clear error, not a crash

## backup --encrypt

- [ ] `backup --port <PORT> --encrypt` prompts for a password and a confirmation
- [ ] A mismatched confirmation re-prompts with "Passwords did not match, try again."
- [ ] An empty password is rejected and re-prompted
- [ ] The resulting backup file has `"encrypted": true` and no readable plaintext config
- [ ] The success message includes "(encrypted)"

## restore / mesh-restore

- [ ] `restore --port <PORT>` (no flags) restores the connected device's own latest backup
- [ ] `restore --port <PORT> --node-id <ID>` restores a specific device's latest backup
- [ ] `restore --port <PORT> --file <path>` restores an exact backup file
- [ ] `--file` and `--node-id` together are rejected (mutually exclusive)
- [ ] Restoring with no backups present for a node id prints "No backups found..." and exits non-zero
- [ ] After restoring, a fresh `backup` shows the config matches what was restored
- [ ] `mesh-restore --port <PORT>` produces the same result as `meshprogrammer restore`

## restore (encrypted backups)

- [ ] Restoring an encrypted backup prompts for "Password: "
- [ ] The correct password decrypts and restores successfully
- [ ] A wrong password prints "Incorrect password." and exits non-zero, device untouched

## list / mesh-list

- [ ] `list` with no backups present prints "No backups found in ..."
- [ ] `list` after one or more backups shows device id(s), backup count(s), and filenames
- [ ] `mesh-list` produces the same output as `meshprogrammer list`
- [ ] `list --working-dir <DIR>` lists backups from that folder instead of `working/`

## export-channels / mesh-export-channels

- [ ] `export-channels --port <PORT> <name>` succeeds, writes `working/channels/<name>.json`
- [ ] Re-running with the same name overwrites the file
- [ ] `mesh-export-channels --port <PORT> <name>` produces the same result
- [ ] `export-channels --port <PORT> --working-dir <DIR> <name>` writes under `<DIR>/channels/`

## export-channels --encrypt

- [ ] `export-channels --port <PORT> --encrypt <name>` prompts for password + confirmation
- [ ] The resulting file has `"encrypted": true` and no readable plaintext `channel_url`
- [ ] The success message includes "(encrypted)"

## import-channels / mesh-import-channels

- [ ] `import-channels --port <PORT> <name>` applies the saved channel set
- [ ] After importing, exporting again from the same device shows matching channel settings (psk, name, uplink/downlink, position precision) -- LoRa modem fields (bandwidth/spreadFactor/codingRate) may now be explicit where they weren't before; that's expected firmware behavior, not a bug
- [ ] Importing a name that doesn't exist prints "No saved channel set named '<name>' ..." and exits non-zero
- [ ] (If you have a second device) export from device A, then import onto device B -- B's channels now match A's
- [ ] `mesh-import-channels --port <PORT> <name>` produces the same result

## import-channels (encrypted)

- [ ] Importing an encrypted channel set prompts for "Password: "
- [ ] The correct password decrypts and applies successfully
- [ ] A wrong password prints "Incorrect password." and exits non-zero, device untouched

## General

- [ ] `meshprogrammer --help` and each `meshprogrammer <command> --help` show accurate, current usage
- [ ] `uv run pytest` passes
- [ ] `uv run pyright meshprogrammer main.py` reports 0 errors
