# MR3 Control

An unofficial Windows desktop controller for **Edifier MR3** speakers, with a
ConneX-inspired interface and a Windows-style volume overlay.

The app uses Bluetooth Low Energy (BLE) for control. Your audio can keep using
its existing output. The current interface is in **Korean**.

## Features

- Live volume overlay driven by speaker notifications, including physical knob
  changes. **No periodic volume polling.**
- Volume, sound modes, nine-band custom EQ, and acoustic tuning: low cutoff,
  slope, acoustic space, and desktop control.
- Device name and notification sound settings; EQ import/export and settings backups.
- Live BLE discovery, saved devices, and Windows BLE pairing status.
- Tray controls, optional launch at Windows sign-in, start minimized, and
  automatic connection to the last selected speaker.
- Per-user Windows installer, bundled Python runtime, and uninstall support.

Firmware updates and factory reset are not implemented. App self-updating is
not implemented either; install a newer release to update.

## Install

Download `MR3-Control-<version>-Setup-x64.exe` from this repository's **Releases**
page. Requires Windows 10 (1809 or newer) / Windows 11 **x64**, a Bluetooth LE
adapter, and an Edifier MR3. You do not need to install Python.

The installer creates a Start menu shortcut; a desktop shortcut is optional.
**Launch MR3 Control** is checked on the final page. Uncheck it if you prefer to
launch later. Silent installations do not launch the app.

The installer and application are currently **unsigned**, so Windows may display
an unknown-publisher warning. A `SHA256SUMS.txt` file accompanies each release.

On first launch, open the device picker, scan, and select your MR3. Initial
connection may register the control device with Windows through BLE pairing.
The app does not initiate Bluetooth audio pairing or change your default audio
output device.

## Connection limitations

BLE control and Bluetooth audio are separate connections. Depending on the
speaker's state, connecting its Bluetooth audio to a phone or another host may
help make BLE control available. Disconnect other control apps such as Edifier
ConneX before connecting this app: simultaneous control from PC and phone did
not work in testing.

**BLE pairing does not guarantee a successful control connection.** The root
cause of intermittent discovery/reconnection failures has not been established.
The speaker's documented three-minute Bluetooth hidden mode has not been proven
to have identical behavior for BLE control. Do not assume pairing resolves it.

Development testing used an MR3 running firmware **1.0.7**. Other Edifier models
and firmware versions are not guaranteed to work. Scan candidates are identified
by advertised names/service identifiers; MR3 support is checked on connection.

## Everyday use

By default, closing the window leaves the app in the tray. Use the tray menu or
**App settings → Exit** to quit completely. Close it completely before installing
an update or uninstalling; the installer does not forcibly stop it.

Installed user data is stored separately in `%LOCALAPPDATA%\MR3Control`:

- `app-state.json`: saved devices and app preferences
- `app.log`: diagnostic log
- `backups/`: speaker-setting backups

Updates and uninstall leave this data and Windows Bluetooth pairing records in
place. Speaker settings are read from the connected speaker; remembering a device
does not automatically restore an old sound configuration.

No developer device addresses, logs, backups, or research captures are included
in the installer or repository. Logs and backups created during your own use may
contain device identifiers; review them before sharing.

## Run from source

Use Python **3.12 x64** on Windows with Tcl/Tk included:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe mr3_app.py
```

After creating `.venv`, `MR3 Control.vbs` launches without a console. Source runs
store user data beside the source files; those files are excluded from Git.

## Build and release

See [packaging/README.md](packaging/README.md) for local builds and validation.
GitHub Actions tests and builds a Windows installer on pushes to `main`, pull
requests, and manual workflow runs. These runs keep the installer as an Actions
artifact and do not publish a release.

To publish a release, update the single `VERSION` file, commit, then push a
matching tag:

```powershell
# Example: after changing VERSION to 0.1.3 and committing the changes
git push origin main
git tag v0.1.3
git push origin v0.1.3
```

The tag triggers headless tests, a PyInstaller build, a bundled-runtime check,
and Inno Setup packaging. Only after these succeed does the workflow publish a
GitHub Release with the installer and SHA-256 checksum. A tag that does not match
`VERSION` is rejected. No personal access token or signing secret is required;
the publishing job uses the repository's built-in `GITHUB_TOKEN`.

## Credits

This project is not affiliated with or endorsed by Edifier. Edifier names and
the product photograph belong to their respective owner. See
[asset sources](assets/SOURCES.md) for the photograph, Pretendard font license,
and icon origins. Bundled dependency notices are included with the installer.

The public [mEDIFIER project](https://github.com/wh201906/mEDIFIER) was a useful
reference while investigating Edifier BLE behavior; its supported-device claims
should not be interpreted as guarantees for this app or the MR3.
