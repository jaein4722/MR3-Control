# Windows packaging

The installer wraps a PyInstaller one-folder x64 application in Inno Setup.
It bundles Python, Tk, Bleak/WinRT, Pillow, pystray, images, fonts, and dependency
notices. Installation is per-user and does not require administrator rights.

## Local build

Use Windows x64 and Python 3.12 x64 with Tcl/Tk:

```powershell
python -m venv .build-venv
.\.build-venv\Scripts\python.exe -m pip install -r packaging/requirements-build.txt
.\packaging\setup-inno.ps1
.\packaging\build.ps1
```

`setup-inno.ps1` downloads the official Inno Setup 6.7.3 installer, verifies its
pinned SHA-256, and prepares the compiler in `build-tools/InnoSetup` using its
[portable mode](https://jrsoftware.org/ishelp/topic_technotes.htm).
Alternatively, pass `-Iscc 'C:\path\to\ISCC.exe'` to `build.ps1`.

`VERSION` is the version source. `prepare_version.py` renders the version-resource
and manifest templates into `build/`; do not edit version numbers elsewhere.
The installer keeps the same AppId across releases so new versions update the
existing installation.

Outputs:

- `dist/MR3 Control/`: application and its private runtime
- `release/MR3-Control-<version>-Setup-x64.exe`: installer
- `release/SHA256SUMS.txt`: installer checksum
- `build/package-self-test.json`: bundled-runtime validation result

The completion page offers **Launch MR3 Control**, checked by default. It only
runs when the user finishes the wizard with the option selected. Silent setup
skips launch. Start menu shortcuts are included; desktop shortcuts are optional.

## Automated release

`.github/workflows/release.yml` builds on `main`, pull requests, manual dispatch,
and `v*` tags. Only a pushed tag matching `v` + `VERSION` publishes a Release.
The build job has read-only repository permissions; only the separate publishing
job has `contents: write`. Official GitHub actions are pinned to commit hashes.

The workflow uses a fresh Windows runner and an isolated build environment,
runs the headless tests below, builds, and checks the frozen runtime before
uploading the installer. The publishing job checks SHA-256 before attaching the
files to the tagged release. To fix an already published version, bump VERSION
and publish a new tag rather than replacing an existing installer.

## Headless validation

```powershell
.\.build-venv\Scripts\python.exe -m unittest test_overlay test_packaging test_client test_pairing test_device_model test_protocol test_eq_write test_volume_write test_release
```

`build.ps1` also launches the frozen EXE with `--self-test REPORT_PATH` in hidden
mode. This only imports dependencies, starts a Tcl interpreter (no Tk windows),
decodes assets, and renders an overlay into memory. It does not create the app,
tray, or a Bluetooth session; pair a device; touch startup registration; or
activate an existing app. It writes only the requested report.

The general GUI tests are intentionally excluded from this command. Do not run
GUI tests on an active user's desktop. Headless checks cannot certify live BLE,
visible rendering, or the complete install/uninstall experience on a clean PC.

## Data and redistribution

User data lives in `%LOCALAPPDATA%\MR3Control` for installed builds. Source runs
keep data beside the sources. Bundled resources are separate from user data.
The package excludes personal settings, Bluetooth identifiers, logs, backups,
and research APKs/captures.

Quit from the tray before updating or removing the app. The installer checks the
app mutex and does not forcibly stop a running process. Uninstall removes the
login-startup entry only when it points to this installation; it leaves user data
and Bluetooth bonds untouched.

The output is unsigned; no code-signing certificate is configured. Third-party
notices are bundled under `_internal/licenses` and `assets/fonts`. The Edifier
product photograph remains Edifier's property. This application is unofficial.
