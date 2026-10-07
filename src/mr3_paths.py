"""Bundled resources are read-only; installed user data survives upgrades."""
import os
import sys
from pathlib import Path

RESOURCE_DIR = (Path(__file__).resolve().parent if getattr(sys, 'frozen', False)
                else Path(__file__).resolve().parent.parent)


def data_directory():
    if getattr(sys, 'frozen', False):
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
        return base / 'MR3Control'
    return RESOURCE_DIR


DATA_DIR = data_directory()
