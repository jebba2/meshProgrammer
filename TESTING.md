# Manual Test Plan

`meshvault/storage.py`, `backup.py`, `crypto.py`, and the non-hardware parts of `cli.py` are covered by automated tests (`uv run pytest`). `device.py` and the hardware-touching CLI handlers are not -- they require a real Meshtastic device over USB serial or BLE. Run through this checklist against real hardware whenever device-facing behavior changes.

## Prerequisites

- [ ] At least one Meshtastic device connected via USB serial
- [ ] (Optional, for cross-device tests) a second Meshtastic device
- [ ] (Optional, for BLE tests) a Meshtastic device with Bluetooth enabled, paired/in range
- [ ] `uv sync` has been run
- [ ] Noted the device's serial port (e.g. `COM5`) from `scan` below

All commands below need the `uv run` prefix shown (e.g. `uv run meshvault-scan`, `uv run meshvault scan`) -- the `meshvault`/`meshvault-*` commands only exist inside this project's virtual environment, so a bare `scan` or `backup --port COM5` typed directly in your shell will fail with a "not recognized" error, unless you've activated the venv or installed via `uv tool install --editable .` (see [README.md Setup](README.md#setup) for both options). If you've done either, drop the `uv run` prefix from every command below.

## help / meshvault-help

- [ ] `uv run meshvault help` lists every command (help, scan, backup, restore, list, device-backups, list-channels, export-channels, import-channels, gui, meshtastic-web) with a one-line description
- [ ] `uv run meshvault-help` produces the same output
- [ ] Output matches `uv run meshvault --help`
- [ ] Output mentions `--port`, `--ble`, and `--encrypt` and which commands accept them

## scan / meshvault-scan

- [ ] `uv run meshvault scan` lists the connected device's port
- [ ] `uv run meshvault-scan` produces the same result
- [ ] Unplug the device; `uv run meshvault-scan` reports "No Meshtastic devices detected."
- [ ] `uv run meshvault-scan --working-dir /tmp` is rejected (scan doesn't accept this flag)
- [ ] `uv run meshvault-scan --ble` lists the connected device's BLE name and address (takes ~10 seconds)
- [ ] With no BLE device nearby, `uv run meshvault-scan --ble` reports "No Meshtastic BLE devices detected."

## backup / meshvault-backup

`--port` is optional throughout: if omitted and exactly one Meshtastic device is connected, its port is used automatically.

- [ ] `uv run meshvault-backup [--port <PORT>]` succeeds, printing the node id and backup path
- [ ] The backup file exists at `working/<node-id>/backup-<timestamp>.json`
- [ ] The backup file contains `local_config`, `module_config`, owner name, and `channel_url`
- [ ] Running it twice creates two distinct timestamped files (not an overwrite)
- [ ] `uv run meshvault backup [--port <PORT>]` produces the same result as `meshvault-backup`
- [ ] `uv run meshvault-backup [--port <PORT>] --working-dir <DIR>` writes under `<DIR>/<node-id>/` instead of `working/`
- [ ] `uv run meshvault-backup --port <bad-port>` fails with a clear error, not a crash

## backup --encrypt

- [ ] `uv run meshvault-backup [--port <PORT>] --encrypt` prompts for a password and a confirmation
- [ ] A mismatched confirmation re-prompts with "Passwords did not match, try again."
- [ ] An empty password is rejected and re-prompted
- [ ] The resulting file is named `encryptedbackup-<timestamp>.json`, not `backup-<timestamp>.json`
- [ ] The resulting backup file has `"encrypted": true` and no readable plaintext config
- [ ] The success message includes "(encrypted)"
- [ ] With both encrypted and plain backups present for a device, `uv run meshvault-list` and `restore`'s "latest backup" pick the actual newest one regardless of which prefix it has

## restore / meshvault-restore

`--port` is optional throughout: if omitted and exactly one Meshtastic device is connected, its port is used automatically.

- [ ] `uv run meshvault-restore [--port <PORT>]` (no other flags) restores the connected device's own latest backup
- [ ] `uv run meshvault-restore [--port <PORT>] --node-id <ID>` restores a specific device's latest backup
- [ ] `uv run meshvault-restore [--port <PORT>] --file <path>` restores an exact backup file
- [ ] `--file` and `--node-id` together are rejected (mutually exclusive)
- [ ] Restoring with no backups present for a node id prints "No backups found..." and exits non-zero
- [ ] After restoring, a fresh `uv run meshvault-backup [--port <PORT>]` shows the config matches what was restored
- [ ] `uv run meshvault restore [--port <PORT>]` produces the same result as `meshvault-restore`

## restore (encrypted backups)

- [ ] Restoring an encrypted backup prompts for "Password: "
- [ ] The correct password decrypts and restores successfully
- [ ] A wrong password prints "Incorrect password." and exits non-zero, device untouched

## list / meshvault-list

- [ ] `uv run meshvault-list` with no backups present prints "No backups found in ..."
- [ ] `uv run meshvault-list` after one or more backups shows device id(s), backup count(s), and filenames
- [ ] `uv run meshvault list` produces the same output as `meshvault-list`
- [ ] `uv run meshvault-list --working-dir <DIR>` lists backups from that folder instead of `working/`

## device-backups / meshvault-device-backups

`--port` is optional throughout: if omitted and exactly one Meshtastic device is connected, its port is used automatically.

- [ ] `uv run meshvault-device-backups [--port <PORT>]` lists only the connected device's own backups, not other devices' from `working/`
- [ ] With no backups for the connected device, prints "No backups found for <node-id> in working"
- [ ] `uv run meshvault device-backups [--port <PORT>]` produces the same result as `meshvault-device-backups`
- [ ] `uv run meshvault-device-backups [--port <PORT>] --working-dir <DIR>` lists backups from that folder instead of `working/`
- [ ] With no device connected, prints "No Meshtastic devices detected. Specify --port." and exits non-zero
- [ ] (If you have a second device) with two devices connected and no `--port`, prints "Multiple devices detected (...). Specify --port to choose one." and exits non-zero

## list-channels / meshvault-list-channels

- [ ] `uv run meshvault-list-channels` with no saved channel sets prints "No channel sets found in working/channels"
- [ ] After `export-channels`, `uv run meshvault-list-channels` lists the saved name
- [ ] An encrypted channel set is shown as `<name> (encrypted)`; a plain one has no suffix
- [ ] `uv run meshvault list-channels` produces the same output as `meshvault-list-channels`
- [ ] `uv run meshvault-list-channels --working-dir <DIR>` lists channel sets from that folder instead of `working/`
- [ ] Doesn't require a device connected

## export-channels / meshvault-export-channels

`--port` is optional throughout: if omitted and exactly one Meshtastic device is connected, its port is used automatically.

- [ ] `uv run meshvault-export-channels [--port <PORT>] <name>` succeeds, writes `working/channels/<name>.json`
- [ ] Re-running with the same name overwrites the file
- [ ] `uv run meshvault export-channels [--port <PORT>] <name>` produces the same result
- [ ] `uv run meshvault-export-channels [--port <PORT>] --working-dir <DIR> <name>` writes under `<DIR>/channels/`

## export-channels --encrypt

- [ ] `uv run meshvault-export-channels [--port <PORT>] --encrypt <name>` prompts for password + confirmation
- [ ] The resulting file has `"encrypted": true` and no readable plaintext `channel_url`
- [ ] The success message includes "(encrypted)"

## import-channels / meshvault-import-channels

`--port` is optional throughout: if omitted and exactly one Meshtastic device is connected, its port is used automatically.

- [ ] `uv run meshvault-import-channels [--port <PORT>] <name>` applies the saved channel set
- [ ] After importing, exporting again from the same device shows matching channel settings (psk, name, uplink/downlink, position precision) -- LoRa modem fields (bandwidth/spreadFactor/codingRate) may now be explicit where they weren't before; that's expected firmware behavior, not a bug
- [ ] Importing a name that doesn't exist prints "No saved channel set named '<name>' ..." and exits non-zero
- [ ] (If you have a second device) export from device A, then import onto device B -- B's channels now match A's
- [ ] `uv run meshvault import-channels [--port <PORT>] <name>` produces the same result as `meshvault-import-channels`

## import-channels (encrypted)

- [ ] Importing an encrypted channel set prompts for "Password: "
- [ ] The correct password decrypts and applies successfully
- [ ] A wrong password prints "Incorrect password." and exits non-zero, device untouched

## --port auto-detection edge cases

- [ ] With no device connected, `uv run meshvault-backup` (no `--port`) prints "No Meshtastic devices detected. Specify --port." and exits non-zero
- [ ] (If you have a second device) with two devices connected, `uv run meshvault-backup` (no `--port`) prints "Multiple devices detected (<PORT1>, <PORT2>). Specify --port to choose one." and exits non-zero
- [ ] In both cases above, no backup file is written and the device(s) are untouched
- [ ] The same no-device/multiple-device behavior holds for `meshvault-restore`, `meshvault-device-backups`, `meshvault-export-channels`, and `meshvault-import-channels`

## --ble

- [ ] `uv run meshvault-backup --ble` connects over Bluetooth to the only nearby Meshtastic BLE device and succeeds
- [ ] `uv run meshvault-backup --ble "<device name>"` connects to that specific device by its advertised name
- [ ] `uv run meshvault-backup --port COM5 --ble` is rejected (mutually exclusive)
- [ ] With no BLE device nearby, `uv run meshvault-backup --ble` fails with a clear error (not a crash), e.g. mentioning "No Meshtastic BLE peripheral ... found"
- [ ] (If you have a second BLE device) with two BLE devices nearby, `uv run meshvault-backup --ble` (no name) fails with a clear "More than one Meshtastic BLE peripheral ... found" error
- [ ] The same --ble behavior (connect, name selection, mutual exclusion with --port, clear errors) holds for `meshvault-restore`, `meshvault-device-backups`, `meshvault-export-channels`, and `meshvault-import-channels`
- [ ] For `meshvault-export-channels`/`meshvault-import-channels`, the channel-set name must come before `--ble` (e.g. `meshvault-export-channels office --ble`), or use `--ble=<name>` -- putting it after a bare `--ble <value>` gets swallowed as the BLE device name instead of the channel-set name

## gui / meshvault-gui

The GUI covers all 8 device/storage commands above through a browser instead of the terminal -- run through each action below at least once against real hardware.

- [ ] `uv run meshvault-gui` prints a `http://127.0.0.1:<port>/` URL and opens it in the default browser automatically
- [ ] `uv run meshvault gui` produces the same result
- [ ] `uv run meshvault-gui --http-port 8765` serves on that exact port instead of an OS-assigned one
- [ ] `uv run meshvault-gui --working-dir <DIR>` reads/writes backups and channel sets under `<DIR>` instead of `working/`
- [ ] `meshvault-gui` also starts the meshtastic-web client alongside it (prints a second "Meshtastic web client running at ..." line); clicking "Open Meshtastic Web Client" in the page opens a working app, no manual `meshvault-meshtastic-web` needed
- [ ] Stopping `meshvault-gui` (Ctrl+C) stops the meshtastic-web sidecar too -- its port stops responding
- [ ] With no network and no prior cache, `meshvault-gui` still starts and works normally (just without the meshtastic-web client), printing a "couldn't download it" warning instead of crashing
- [ ] With `meshvault-meshtastic-web` already running separately on its default port, starting `meshvault-gui` doesn't error -- it prints a "port unavailable, assuming it's already running separately" warning and the existing one keeps working
- [ ] The server is unreachable from another machine on the LAN (e.g. try `http://<this-machine's-LAN-IP>:<port>/` from a second device -- it should fail to connect, confirming it's bound to 127.0.0.1 only, not 0.0.0.0)
- [ ] The dashboard's "Known devices and backups" and "Saved channel sets" lists match `meshvault-list`/`meshvault-list-channels` output, and their Refresh buttons pick up new entries without reloading the page
- [ ] Scanning serial ports lists the connected device's port; scanning BLE (~10s) shows a spinner/disabled button for the duration and then lists nearby devices
- [ ] Backup (plain) succeeds and the new file shows up after refreshing the dashboard
- [ ] Backup with "Encrypt" checked and a password succeeds; the saved file is encrypted (matches the `--encrypt` CLI behavior)
- [ ] Backup with "Encrypt" checked but no password shows an error and does not touch the device
- [ ] Restore "connected device's own latest backup" succeeds and a fresh backup afterward matches what was restored
- [ ] Restore "latest backup for node id" and restore "specific backup file" both succeed for the right target
- [ ] Restoring an encrypted backup with no password shows an "enter the password" prompt without touching the device; a wrong password shows "Incorrect password" and lets you retry; the correct password restores successfully
- [ ] "List backups for connected device" matches `meshvault-device-backups` output
- [ ] Export channels (plain and encrypted) writes a channel set visible in "Saved channel sets" after refreshing
- [ ] Import channels (plain) applies successfully; an encrypted set follows the same needs-password / wrong-password / correct-password flow as restore
- [ ] Closing the terminal (Ctrl+C) running `meshvault-gui` stops the server -- the page stops responding

## meshtastic-web / meshvault-meshtastic-web

This launches a separate, third-party project (the official Meshtastic web client) -- it doesn't need a Meshtastic device connected to test the basics, but a connected device (and pairing it inside that client via Web Serial/Web Bluetooth) is needed to confirm it's actually usable end-to-end.

- [ ] First run, with no prior cache: `uv run meshvault-meshtastic-web` downloads the release, prints a `http://127.0.0.1:8766/` URL, and opens it in your default browser -- requires network access
- [ ] `<working-dir>/.meshtastic-web-client/v2.7.1/` (or whatever `--client-version` you used) now contains `index.html` and no leftover `.gz` files
- [ ] Stop it (Ctrl+C) and run it again: it starts immediately, without re-downloading (no network activity)
- [ ] The page loads the Meshtastic web client UI (not a blank page or a 404)
- [ ] Visiting a deep link directly, e.g. `http://127.0.0.1:8766/messages/broadcast/0`, loads the app shell instead of a 404 (confirms the SPA fallback works)
- [ ] `uv run meshvault meshtastic-web` produces the same result as `meshvault-meshtastic-web`
- [ ] `uv run meshvault-meshtastic-web --http-port 9000` serves on that port instead of the default `8766`
- [ ] `uv run meshvault-meshtastic-web --client-version <a different valid tag>` downloads and caches that version separately, without touching the `v2.7.1` cache
- [ ] `uv run meshvault-meshtastic-web --client-version not-a-real-tag` fails with a clear "Failed to download ..." error, not a raw traceback
- [ ] The server is unreachable from another machine on the LAN (bound to 127.0.0.1 only, like `gui`)
- [ ] In `meshvault-gui`'s web UI, the "Open Meshtastic Web Client" link (at the top of the page) opens this same client, when `meshvault-meshtastic-web` is running on its default port
- [ ] Inside the Meshtastic web client, connecting to your actual device (Web Serial or Web Bluetooth) and sending a broadcast message works

## General

- [ ] `uv run meshvault --help` and each `meshvault <command> --help` show accurate, current usage
- [ ] `uv run pytest` passes
- [ ] `uv run pyright meshvault main.py` reports 0 errors
