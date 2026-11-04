"""Opt-in per-user startup. No administrator rights required."""
import subprocess
import sys
from pathlib import Path
import winreg

KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
NAME = 'TwistType'


def command():
    if getattr(sys, 'frozen', False):
        args = [sys.executable, '--background']
    else:
        pythonw = Path(sys.executable).with_name('pythonw.exe')
        args = [str(pythonw), str(Path(__file__).with_name('twisttype.py')), '--background']
    return subprocess.list2cmdline(args)


def enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as key:
            return winreg.QueryValueEx(key, NAME)[0] == command()
    except FileNotFoundError:
        return False


def set_enabled(value):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, KEY) as key:
        if value:
            winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(key, NAME)
            except FileNotFoundError:
                pass
