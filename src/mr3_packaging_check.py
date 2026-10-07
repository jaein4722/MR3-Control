"""Check the installed runtime without starting Tk, a tray, or a BLE session."""
import importlib
import json
import sys
import traceback
from pathlib import Path


def run(report_path):
    report = {'ok': False, 'frozen': bool(getattr(sys, 'frozen', False)), 'checks': []}
    try:
        modules = ('tkinter', '_tkinter', 'PIL.Image', 'PIL.ImageTk', 'pystray._win32',
                   'bleak.backends.winrt.client', 'bleak.backends.winrt.scanner',
                   'winrt.windows.devices.bluetooth',
                   'winrt.windows.devices.bluetooth.advertisement',
                   'winrt.windows.devices.bluetooth.genericattributeprofile',
                   'winrt.windows.devices.enumeration', 'winrt.windows.devices.radios',
                   'winrt.windows.foundation', 'winrt.windows.foundation.collections',
                   'winrt.windows.storage.streams', 'mr3_app', 'mr3_ui', 'mr3_devices',
                   'mr3_startup', 'mr3_instance')
        for name in modules:
            importlib.import_module(name)
            report['checks'].append(name)
        from mr3_paths import DATA_DIR, RESOURCE_DIR
        from mr3_startup import startup_command
        from PIL import Image
        import tkinter
        # Tcl() initializes the interpreter only, never Tk/windowing.
        interp = tkinter.Tcl()
        report['tcl_version'] = interp.eval('info patchlevel')
        if report['frozen']:
            for relative in ('_tcl_data/init.tcl', '_tk_data/tk.tcl', 'licenses/NOTICE.txt',
                             'licenses/MR3-Control-LICENSE.txt', 'licenses/THIRD_PARTY_NOTICES.md',
                             'assets/fonts/LICENSE.txt'):
                assert (RESOURCE_DIR / relative).is_file(), relative
        for name in ('mr3.ico', 'mr3.png', 'mr3-product.png'):
            with Image.open(RESOURCE_DIR / 'assets' / name) as img:
                img.load()
                report['checks'].append(f'{name}: {img.size}')
        for name in ('Regular', 'Medium', 'SemiBold', 'Bold'):
            assert (RESOURCE_DIR / 'assets/fonts' / f'Pretendard-{name}.ttf').is_file()
        from mr3_overlay import render_overlay
        overlay = render_overlay(13,scale=1.5)
        assert overlay.size == (534,132)
        assert len(overlay.convert('RGBa').tobytes('raw','BGRa')) == 534*132*4
        report['checks'].append('overlay RGBA renderer (no window)')
        report['data_directory'] = str(DATA_DIR)
        report['startup_command'] = startup_command()
        if report['frozen']:
            assert not (RESOURCE_DIR / 'app-state.json').exists()
            assert not (RESOURCE_DIR / 'app.log').exists()
            assert not (RESOURCE_DIR / 'backups').exists()
        report['ok'] = True
    except Exception:
        report['error'] = traceback.format_exc()
    Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report['ok'] else 1
