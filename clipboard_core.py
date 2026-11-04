"""Bounded clipboard history, conservative secret filtering, and user-scoped DPAPI."""
from __future__ import annotations

import base64
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
import uuid

MAX_ITEM = 1_048_576
PASSWORD_APPS = {'keepass.exe', 'keepassxc.exe', '1password.exe', 'bitwarden.exe',
                 'dashlane.exe', 'lastpass.exe', 'protonpass.exe', 'nordpass.exe', 'enpass.exe'}
SECRET_MARKERS = ('ExcludeClipboardContentFromMonitorProcessing',
                  'application/x-kde-passwordManagerHint', 'x-kde-passwordManagerHint',
                  'org.nspasteboard.ConcealedType', 'org.nspasteboard.TransientType')


def likely_secret(text: str, strict=True) -> bool:
    value = text.strip()
    if not value:
        return False
    if re.search(r'(?i)(?:password|passwd|passphrase|secret|api[_ -]?key|access[_ -]?token|authorization)\s*[:=]', value):
        return True
    if 'PRIVATE KEY-----' in value or re.search(r'\beyJ[\w-]+\.[\w-]+\.[\w-]+\b', value):
        return True
    if re.match(r'(?i)^(?:sk-[\w-]{12,}|gh[pousr]_[\w]{12,}|AKIA[A-Z0-9]{16})$', value):
        return True
    if re.fullmatch(r'\d{4,8}', value):
        return True
    if re.match(r'https?://', value, re.I):
        from urllib.parse import urlsplit, parse_qsl
        try:
            url = urlsplit(value)
            return bool(url.username or url.password or any(
                re.search(r'(?i)token|password|secret|api.?key|auth|code', key)
                for key, _ in parse_qsl(url.query)))
        except ValueError:
            return True
    if not re.search(r'\s', value):
        groups = sum((bool(re.search(r'[a-z]', value)), bool(re.search(r'[A-Z]', value)),
                      bool(re.search(r'\d', value)), bool(re.search(r'[^\w]', value))))
        return strict or (len(value) >= 8 and groups >= 3)
    return False


class BLOB(C.Structure):
    _fields_ = [('cbData', W.DWORD), ('pbData', C.POINTER(C.c_ubyte))]


def crypt(data: bytes, decrypt=False) -> bytes:
    dll = C.WinDLL('crypt32', use_last_error=True)
    kernel = C.WinDLL('kernel32', use_last_error=True)
    buffer = C.create_string_buffer(data)
    source = BLOB(len(data), C.cast(buffer, C.POINTER(C.c_ubyte)))
    result = BLOB()
    fn = dll.CryptUnprotectData if decrypt else dll.CryptProtectData
    fn.restype = W.BOOL
    fn.argtypes = [C.POINTER(BLOB), C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p, W.DWORD, C.POINTER(BLOB)]
    kernel.LocalFree.argtypes, kernel.LocalFree.restype = [C.c_void_p], C.c_void_p
    if not fn(C.byref(source), None, None, None, None, 1, C.byref(result)):
        raise OSError('Windows could not decrypt clipboard history.' if decrypt else 'Windows could not encrypt clipboard history.')
    try:
        return C.string_at(result.pbData, result.cbData)
    finally:
        kernel.LocalFree(result.pbData)


def valid_item(item):
    if not isinstance(item, dict) or not all(isinstance(item.get(k), str) for k in ('id', 'kind', 'source', 'created')):
        raise ValueError('Invalid clipboard history entry.')
    value, kind = item.get('value'), item['kind']
    if kind == 'text':
        okay = isinstance(value, str) and bool(value.strip()) and len(value.encode('utf-8')) <= MAX_ITEM
    elif kind == 'image':
        try:
            decoded = base64.b64decode(value, validate=True)
            okay = decoded.startswith(b'\x89PNG\r\n\x1a\n') and len(decoded) <= MAX_ITEM
        except (ValueError, TypeError):
            okay = False
    elif kind == 'files':
        okay = (isinstance(value, list) and 0 < len(value) <= 100
                and all(isinstance(v, str) and len(v) < 32768 for v in value)
                and len(json.dumps(value).encode('utf-8')) <= MAX_ITEM)
    else:
        okay = False
    if not okay:
        raise ValueError('Unsupported or oversized clipboard item.')
    return {k: item[k] for k in ('id', 'kind', 'value', 'source', 'created')}


class HistoryStore:
    def __init__(self, path: Path | None = None, limit=20, strict=True):
        self.path, self.limit, self.strict = path, limit, strict
        self.items = []
        self.error = ''

    def load(self):
        if not self.path or not self.path.exists():
            return
        try:
            if self.path.stat().st_size > 80_000_000:
                raise ValueError('History file exceeds the size limit.')
            raw = json.loads(crypt(self.path.read_bytes(), decrypt=True))
            if not isinstance(raw, dict) or raw.get('version') != 1 or not isinstance(raw.get('items'), list) or len(raw['items']) > 50:
                raise ValueError('Invalid history format.')
            # Reapply current policy before anything can be displayed.
            self.items = [valid_item(i) for i in raw['items']]
            self.items = [i for i in self.items if i['kind'] != 'text' or not likely_secret(i['value'], self.strict)][:self.limit]
        except Exception:
            self.items = []
            self.error = 'Stored history could not be opened. Clear history to start again; the existing encrypted file is preserved.'

    def save(self):
        if self.error:
            raise OSError(self.error)
        if not self.path:
            return
        payload = crypt(json.dumps({'version': 1, 'items': self.items}, ensure_ascii=False).encode('utf-8'))
        fd, temp = tempfile.mkstemp(prefix='.twisttype-clip-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'wb') as file:
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp, self.path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)

    def add(self, kind, value, source='Unknown app'):
        if self.error or source.casefold() in PASSWORD_APPS or (kind == 'text' and likely_secret(value, self.strict)):
            return False
        item = valid_item(dict(id=str(uuid.uuid4()), kind=kind, value=value, source=source[:120],
                               created=datetime.now(timezone.utc).isoformat()))
        self.items = [i for i in self.items if not (i['kind'] == kind and i['value'] == value)]
        self.items.insert(0, item)
        self.items = self.items[:self.limit]
        return True

    def remove(self, ident):
        self.items = [i for i in self.items if i['id'] != ident]
        self.save()

    def clear(self):
        self.items = []
        self.error = ''
        self.save()

    def configure(self, limit, strict):
        self.limit, self.strict = limit, strict
        self.items = [i for i in self.items if i['kind'] != 'text' or not likely_secret(i['value'], strict)][:limit]


def preview(item):
    if item['kind'] == 'image':
        return 'Image copied to clipboard'
    if item['kind'] == 'files':
        names = [Path(p).name for p in item['value']]
        return ', '.join(names)[:100]
    return ' '.join(item['value'].split())[:100]
