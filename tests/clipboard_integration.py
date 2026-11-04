"""Live Qt/Windows metadata and hotkey tests. Restore Qt-exposed clipboard formats.
All captured entries are synthetic test samples, kept in memory only.
"""
import ctypes as C
from ctypes import wintypes as W
import json
import subprocess
import tempfile
import time
from pathlib import Path
import sys
import faulthandler

faulthandler.dump_traceback_later(20, repeat=True)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QByteArray, QMimeData, Qt, QUrl
from PySide6.QtGui import QImage, QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit
from clipboard_core import HistoryStore
from clipboard_service import ClipboardService, clipboard_metadata, source_context
from clipboard_ui import ClipboardPicker
from core import DEFAULT_SETTINGS
from win_engine import INPUT, bind, kernel, key_event, user

app = QApplication([])
print('Clipboard check: preserving current formats', flush=True)
ole = C.OleDLL('ole32')
original = QMimeData()
current = app.clipboard().mimeData()
if current:
    for name in current.formats():
        original.setData(name, current.data(name))
    if current.hasImage():
        original.setImageData(QImage(current.imageData()).copy())
    if current.hasUrls():
        original.setUrls(current.urls())
    if current.hasText():
        original.setText(current.text())
    if current.hasHtml():
        original.setHtml(current.html())
target = QLineEdit()
target.setWindowTitle('TwistType clipboard integration target')
target.show()
target.activateWindow()
target.setFocus()
QTest.qWait(100)
history = HistoryStore()
service = ClipboardService(history, dict(DEFAULT_SETTINGS))
triggered = []
service.quick_access.connect(lambda: triggered.append(True))
checks = []

def tick():
    QTest.qWait(250)

try:
    print('Clipboard check: notifications and privacy', flush=True)
    service.start()
    assert service.hotkeys.registered, 'Default clipboard hotkey is unavailable on this PC.'
    for i in range(23):
        app.clipboard().setText(f'Clipboard test note number {i}')
        tick()
    assert len(history.items) == 20, (len(history.items), service.status)
    assert history.items[0]['value'] == 'Clipboard test note number 22'
    checks.append('Real clipboard notifications retain latest 20 copies')
    assert source_context().casefold() == 'python.exe'
    checks.append('Source process identification')
    before = list(history.items)
    for text in ('password: synthetic test only', 'P@ssw0rd-Example', '123456'):
        app.clipboard().setText(text)
        tick()
    assert history.items == before
    checks.append('Likely secrets never appear in history')
    for name, value in (('ExcludeClipboardContentFromMonitorProcessing', b'1'),
                        ('CanIncludeInClipboardHistory', b'\0\0\0\0')):
        mime = QMimeData()
        mime.setText('Ordinary text tagged as sensitive by source app')
        mime.setData(f'application/x-qt-windows-mime;value="{name}"', QByteArray(value))
        app.clipboard().setMimeData(mime)
        tick()
        assert clipboard_metadata() is True, name
        assert history.items == before, name
        checks.append('Honors ' + name)
    image = QImage(10, 10, QImage.Format.Format_ARGB32)
    image.fill(QColor('#37318C'))
    app.clipboard().setImage(image)
    tick()
    assert history.items[0]['kind'] == 'image', service.status
    image_entry = history.items[0]
    checks.append('Captures image as bounded PNG')
    service.copy_item(image_entry)
    tick()
    assert app.clipboard().image().size() == image.size()
    checks.append('Restores image with sensitive metadata')
    assert clipboard_metadata() is True
    text_entry = next(i for i in history.items if i['kind'] == 'text')
    size_before = len(history.items)
    service.copy_item(text_entry)
    tick()
    assert app.clipboard().text() == text_entry['value']
    assert len(history.items) == size_before
    checks.append('Restores text without recapturing history entry')
    service.suspended = True
    before = list(history.items)
    app.clipboard().setText('Paused clipboard sample text')
    tick()
    assert history.items == before
    service.suspended = False
    checks.append('Pause stops new capture')
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(ROOT / 'README.md'))])
    print('Clipboard check: file paths', flush=True)
    app.clipboard().setMimeData(mime)
    tick()
    assert history.items[0]['kind'] == 'files', (service.status, source_context(), clipboard_metadata(), app.clipboard().mimeData().formats())
    copied = []
    service.copy_item(history.items[0], on_ready=lambda: copied.append(True))
    for retry in range(40):
        tick()
        if copied:
            break
    assert copied, service.status
    replayed_urls = app.clipboard().mimeData().urls()
    assert replayed_urls, (history.items[0], app.clipboard().mimeData().formats(), service.status)
    assert replayed_urls[0].toLocalFile().replace('\\', '/') == str(ROOT / 'README.md').replace('\\', '/')
    checks.append('Captures and restores copied file paths')
    picker = ClipboardPicker(service)
    print('Clipboard check: hotkey and picker', flush=True)
    service.quick_access.connect(picker.open_picker)
    events = (INPUT * 6)(key_event(0x11), key_event(0x12), key_event(0x56),
                         key_event(0x56, flags=2), key_event(0x12, flags=2), key_event(0x11, flags=2))
    assert user.SendInput(len(events), events, C.sizeof(INPUT)) == len(events)
    tick()
    assert triggered, 'Global keyboard shortcut did not emit quick-access event.'
    assert picker.isVisible()
    checks.append('Ctrl+Alt+V delivers WM_HOTKEY to quick access')
    QTest.keyClick(picker.search, Qt.Key.Key_Down)
    assert picker.list.currentRow() == 1
    QTest.keyClick(picker.search, Qt.Key.Key_Up)
    assert picker.list.currentRow() == 0
    QTest.keyClick(picker, Qt.Key.Key_Escape)
    assert not picker.isVisible()
    checks.append('Keyboard picker supports arrows and Escape')
    with tempfile.TemporaryDirectory(prefix='twisttype-paste-test-') as directory:
        print('Clipboard check: paste target', flush=True)
        directory = Path(directory)
        child = subprocess.Popen([sys.executable, str(ROOT / 'tests' / 'windows_integration.py'), '--target', str(directory)])
        def read(name):
            try:
                return json.loads((directory / name).read_text(encoding='utf-8'))
            except (ValueError, OSError):
                return {}
        def wait_for(fn):
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                if fn():
                    return
                QTest.qWait(40)
            raise AssertionError('Dedicated paste target timed out: ' + str(read('snapshot.json')) + ' / ' + service.status)
        try:
            wait_for(lambda: read('ready.json').get('hwnd'))
            (directory / 'command.json').write_text(json.dumps({'seq': 1, 'clear': True, 'focus': 0}))
            wait_for(lambda: read('snapshot.json').get('seq') == 1)
            hwnd = read('ready.json')['hwnd']
            bind(user, 'AttachThreadInput', W.BOOL, W.DWORD, W.DWORD, W.BOOL)
            bind(user, 'BringWindowToTop', W.BOOL, W.HWND)
            current = kernel.GetCurrentThreadId()
            foreground = user.GetWindowThreadProcessId(user.GetForegroundWindow(), None)
            attached = user.AttachThreadInput(current, foreground, True) if current != foreground else False
            try:
                user.BringWindowToTop(hwnd)
                user.SetForegroundWindow(hwnd)
            finally:
                if attached:
                    user.AttachThreadInput(current, foreground, False)
            wait_for(lambda: user.GetForegroundWindow() == hwnd)
            picker.open_picker()
            tick()
            assert picker.target and picker.target[0] == hwnd
            picker.search.setText('Clipboard test note number 22')
            assert picker.list.count() == 1
            picker.choose()
            wait_for(lambda: read('snapshot.json').get('first') == 'Clipboard test note number 22')
            checks.append('Picker restores original app/field and pastes selected text')
        finally:
            picker.close()
            (directory / 'command.json').write_text(json.dumps({'seq': 99, 'quit': True}))
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.terminate()
                child.wait(timeout=3)
finally:
    print('Clipboard check: restoring clipboard', flush=True)
    service.stop()
    restored = False
    for attempt in range(20):
        try:
            if attempt == 0:
                app.clipboard().setMimeData(original)
            QTest.qWait(50)
            ole.OleFlushClipboard()
            restored = True
            break
        except OSError:
            QTest.qWait(50)
    assert restored, 'The test could not restore the original clipboard formats.'
    target.close()
output = {'passed': len(checks), 'checks': checks, 'original_clipboard_restored': True}
(ROOT / 'clipboard-integration-results.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
print(json.dumps(output, indent=2))
faulthandler.cancel_dump_traceback_later()
