"""Per-user Windows login startup registration; no administrator rights needed."""
import os
from pathlib import Path
import subprocess
import sys
import winreg

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
VALUE_NAME = 'MR3 Control'


def startup_command():
    if getattr(sys, 'frozen', False):
        return subprocess.list2cmdline([sys.executable])
    launcher = Path(__file__).resolve().parent / 'MR3 Control.vbs'
    host = Path(os.environ['SystemRoot']) / 'System32' / 'wscript.exe'
    return subprocess.list2cmdline([str(host), str(launcher)])


def is_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            command, kind = winreg.QueryValueEx(key, VALUE_NAME)
        return kind == winreg.REG_SZ and command == startup_command()
    except FileNotFoundError:
        return False


def set_enabled(enabled):
    if enabled:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, startup_command())
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            pass
