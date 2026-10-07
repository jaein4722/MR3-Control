# Tests

From the repository root, with the build dependencies installed:

```powershell
python -m unittest discover -s tests -t .
```

This is the same headless suite used by GitHub Actions. Bluetooth transport is
mocked; EQ and volume round-trip tests never contact a real speaker.

`gui/` contains separate interactive Tk tests. It deliberately has no
`__init__.py`, so unittest discovery does not recurse into it. These tests can
create windows and take focus even when transparent. Run them only on an
isolated test desktop, explicitly:

```powershell
python -m unittest tests.gui.test_app tests.gui.test_devices tests.gui.test_widgets
```
