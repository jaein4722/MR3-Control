# Developer tools

These tools are optional and are not bundled with the application. Run them from
the repository root with the same Python environment as the application.

| Tool | Purpose |
| --- | --- |
| `make_icon.py` | Regenerate the app icon in `assets/` using Pillow. |
| `mr3_diagnostics.py` / `run-diagnostics.ps1` | Scan or inspect BLE devices and save diagnostic reports. |
| `mr3_listen.py` | Connect to an explicitly supplied address and observe notifications. |
| `mr3_eq_test.py` | Hardware experiment: change one EQ band, read it back, and attempt restoration. |
| `mr3_volume_test.py` | Hardware experiment: change volume, read it back, and attempt restoration. |

For example, `python tools/mr3_diagnostics.py --help` describes the available
commands. Hardware tools require explicit invocation; they are not part of CI.
The EQ/volume scripts write real settings when run directly, and interruption or
connection loss can prevent restoration. Their unit tests use fake transports.
Reports are written to the ignored `diagnostics/` directory and may contain
Bluetooth identifiers. Review reports before sharing.
