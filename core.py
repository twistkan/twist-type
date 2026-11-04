"""Offline configuration and deterministic matching. No keyboard or UI dependencies."""
from __future__ import annotations

import copy
import os
from pathlib import Path
import re
import sys
import tempfile
import time

import yaml

DEFAULT_SETTINGS = {
    'trigger_mode': 'delimiter', 'preserve_space': True,
    'excluded_titles': ['Command Prompt', 'PowerShell', 'cmd.exe', 'Terminal', 'KeePass'],
    'excluded_processes': ['cmd.exe', 'powershell.exe', 'pwsh.exe', 'WindowsTerminal.exe',
                           'KeePass.exe', 'KeePassXC.exe', '1Password.exe', 'Bitwarden.exe'],
    'clipboard_enabled': True, 'clipboard_limit': 20, 'clipboard_strict': True,
    'clipboard_hotkey': 'Ctrl+Alt+V',
}


def app_dir() -> Path:
    return Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent


def data_dir() -> Path:
    root = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local') / 'TwistType'
    root.mkdir(parents=True, exist_ok=True)
    return root


def migrate_legacy(destination: Path, candidates=None):
    """One-time, non-destructive migration of the old executable-relative files."""
    destination.mkdir(parents=True, exist_ok=True)
    if (destination / 'snippets.yaml').exists():
        return False
    if candidates is None:
        executable = app_dir()
        candidates = [executable, executable / 'TwistType', executable.parent / 'TwistType']
    for legacy in candidates:
        legacy = Path(legacy)
        source = legacy / 'snippets.yaml'
        if legacy.resolve() == destination.resolve() or not source.is_file():
            continue
        if source.stat().st_size > 2_000_000:
            raise ValueError('Existing snippet file is too large to migrate safely.')
        raw = source.read_bytes()
        validate(yaml.safe_load(raw.decode('utf-8-sig')))
        # Copy history and backup before committing the snippet file. Existing
        # destination files always win; old files are never moved or deleted.
        for name, limit in [('clipboard-history.dat', 80_000_000), ('snippets.yaml.bak', 2_000_000), ('snippets.yaml', 2_000_000)]:
            origin, target = legacy / name, destination / name
            if target.exists() or not origin.is_file():
                continue
            if origin.stat().st_size > limit:
                raise ValueError(f'{name} is too large to migrate safely.')
            fd, temp = tempfile.mkstemp(prefix='.twisttype-migrate-', dir=destination)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(raw if name == 'snippets.yaml' else origin.read_bytes())
                    stream.flush()
                    os.fsync(stream.fileno())
                if not target.exists():
                    os.replace(temp, target)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)
        return True
    return False


def resource_path(name: str) -> Path:
    return Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / name


def validate(data: object) -> dict:
    if not isinstance(data, dict) or data.get('version') != 1:
        raise ValueError('The YAML must contain version: 1, settings, and snippets.')
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    supplied = data.get('settings', {})
    if not isinstance(supplied, dict):
        raise ValueError('Settings must be a mapping.')
    settings.update(supplied)
    if settings['trigger_mode'] not in ('delimiter', 'immediate'):
        raise ValueError('Trigger mode must be delimiter or immediate.')
    if type(settings['preserve_space']) is not bool:
        raise ValueError('preserve_space must be true or false.')
    if any(type(settings[key]) is not bool for key in ('clipboard_enabled', 'clipboard_strict')):
        raise ValueError('Clipboard switches must be true or false.')
    if type(settings['clipboard_limit']) is not int or settings['clipboard_limit'] not in (10, 20, 50):
        raise ValueError('Clipboard capacity must be 10, 20, or 50.')
    if settings['clipboard_hotkey'] not in ('Ctrl+Alt+V', 'Ctrl+Alt+Shift+V'):
        raise ValueError('Choose a supported clipboard shortcut.')
    for key in ('excluded_titles', 'excluded_processes'):
        if not isinstance(settings[key], list) or any(not isinstance(x, str) or not x.strip() for x in settings[key]):
            raise ValueError(f'{key} must be a list of nonempty strings.')
        # Required safety exclusions cannot be removed by an accidental YAML edit.
        settings[key] = list(dict.fromkeys(DEFAULT_SETTINGS[key] + settings[key]))
    snippets = data.get('snippets')
    if not isinstance(snippets, list):
        raise ValueError('Snippets must be a list.')
    ids, shortcuts, cleaned = set(), set(), []
    for item in snippets:
        if not isinstance(item, dict):
            raise ValueError('Each snippet must be a mapping.')
        ident, label, shortcut, text = (item.get(k) for k in ('id', 'label', 'shortcut', 'text'))
        if not isinstance(ident, str) or not ident or ident in ids:
            raise ValueError('Each snippet needs a unique nonempty id.')
        if not isinstance(label, str) or not label.strip():
            raise ValueError('Each snippet needs a name.')
        if not isinstance(shortcut, str) or not re.fullmatch(r'[;:/!.,][!-~]{1,39}', shortcut):
            raise ValueError('Shortcuts must start with ; : / ! . or , and contain 2–40 ASCII characters without spaces.')
        if shortcut in shortcuts:
            raise ValueError(f'Duplicate shortcut: {shortcut}')
        if not isinstance(text, str) or not text or len(text.encode('utf-16-le')) > 16384:
            raise ValueError('Snippet text must contain 1–8192 UTF-16 units.')
        if any(ord(c) < 32 and c not in '\n\r\t' for c in text):
            raise ValueError('Snippet text contains unsupported control characters.')
        ids.add(ident)
        shortcuts.add(shortcut)
        cleaned.append(dict(id=ident, label=label.strip(), shortcut=shortcut, text=text))
    if settings['trigger_mode'] == 'immediate':
        ordered = sorted(shortcuts)
        for a, b in zip(ordered, ordered[1:]):
            if b.startswith(a):
                raise ValueError(f'Immediate mode cannot use overlapping shortcuts: {a} and {b}.')
    return dict(version=1, settings=settings, snippets=cleaned)


class Store:
    def __init__(self, path: Path | None = None):
        self.default_location = path is None
        self.path = path if path is not None else data_dir() / 'snippets.yaml'
        self.data = dict(version=1, settings=copy.deepcopy(DEFAULT_SETTINGS), snippets=[])

    def load(self):
        if self.default_location and not self.path.exists():
            migrate_legacy(self.path.parent)
        if not self.path.exists():
            self.save(yaml.safe_load(resource_path('snippets.yaml').read_text(encoding='utf-8')))
        if self.path.stat().st_size > 2_000_000:
            raise ValueError('Snippet file is too large (maximum 2 MB).')
        candidate = yaml.safe_load(self.path.read_text(encoding='utf-8'))
        self.data = validate(candidate)
        return self.data

    def save(self, data):
        candidate = validate(data)
        text = yaml.safe_dump(candidate, allow_unicode=True, sort_keys=False)
        if len(text.encode('utf-8')) > 2_000_000:
            raise ValueError('Snippet file is too large (maximum 2 MB).')
        descriptor, temp = tempfile.mkstemp(prefix='.twisttype-', suffix='.tmp', dir=self.path.parent)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            if self.path.exists():
                # One previous version; atomic replacement prevents partial YAML files.
                backup = self.path.with_suffix('.yaml.bak')
                backup.write_bytes(self.path.read_bytes())
            os.replace(temp, self.path)
            self.data = candidate
        finally:
            if os.path.exists(temp):
                os.unlink(temp)


class Matcher:
    def __init__(self, data):
        self.configure(data)

    def configure(self, data):
        self.snippets = {s['shortcut']: s['text'] for s in data['snippets']}
        self.mode = data['settings']['trigger_mode']
        self.preserve_space = data['settings']['preserve_space']
        self.reset()

    def reset(self):
        self.buffer = ''
        self.overflow = False
        self.last_time = 0

    def feed(self, key, now=None):
        now = time.monotonic() if now is None else now
        if now - self.last_time > 15:
            self.reset()
        self.last_time = now
        if key == 'BACKSPACE':
            if self.overflow:
                self.reset()
                return None
            self.buffer = self.buffer[:-1]
            return None
        if key in ('SPACE', 'TAB'):
            match = self.snippets.get(self.buffer) if self.mode == 'delimiter' else None
            count = len(self.buffer)
            self.reset()
            if match is not None:
                return count, match + (' ' if key == 'SPACE' and self.preserve_space else '')
            return None
        if len(key) != 1 or not ('!' <= key <= '~'):
            self.reset()
            return None
        if self.overflow:
            return None
        if len(self.buffer) == 40:
            self.buffer = ''
            self.overflow = True
            return None
        self.buffer += key
        if self.mode == 'immediate' and self.buffer in self.snippets:
            result = len(self.buffer) - 1, self.snippets[self.buffer]
            self.reset()
            return result
        return None


def excluded(title, process, settings):
    return (any(s.casefold() in title.casefold() for s in settings['excluded_titles'])
            or process.casefold() in {s.casefold() for s in settings['excluded_processes']})
