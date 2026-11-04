r"""Real hooks/SendInput against a dedicated child window. Test-only synthetic tag is
converted to physical-event metadata by a subclass; production ignores injected input.
No existing app/document or registry entry is modified.
Run: .venv\Scripts\python.exe tests/windows_integration.py
"""
from __future__ import annotations

import copy
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TAG = 0x54455354


def target(directory):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QWidget
    from win_engine import bind, user
    app = QApplication([])
    window = QWidget()
    window.setWindowTitle('TwistType dedicated test target')
    window.resize(600, 400)
    window.show()
    window.activateWindow()
    bind(user, 'CreateWindowExW', W.HWND, W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD,
         C.c_int, C.c_int, C.c_int, C.c_int, W.HWND, W.HMENU, W.HINSTANCE, C.c_void_p)
    bind(user, 'SetFocus', W.HWND, W.HWND)
    bind(user, 'SetWindowTextW', W.BOOL, W.HWND, W.LPCWSTR)
    controls = []
    for i in range(3):
        style = 0x50800000 | (0x20 if i == 2 else 0x200044)
        controls.append(user.CreateWindowExW(0, 'EDIT', '', style, 20, 20 + i * 125,
                                             550, 110 if i < 2 else 35, int(window.winId()), None, None, None))
        assert controls[-1]
    user.SetFocus(controls[0])
    def contents(hwnd):
        text = C.create_unicode_buffer(32768)
        user.GetWindowTextW(hwnd, text, len(text))
        return text.value.replace('\r\n', '\n')
    directory = Path(directory)
    (directory / 'ready.json').write_text(json.dumps({'hwnd': int(window.winId())}))
    seq = -1
    def tick():
        nonlocal seq
        try:
            command = json.loads((directory / 'command.json').read_text())
            if command['seq'] != seq:
                if command.get('quit'):
                    app.quit()
                    return
                seq = command['seq']
                if command.get('clear'):
                    for control in controls:
                        user.SetWindowTextW(control, '')
                window.setWindowTitle(command.get('title', 'TwistType dedicated test target'))
                window.activateWindow()
                user.SetFocus(controls[command.get('focus', 0)])
        except (OSError, ValueError):
            pass
        out = dict(zip(('first', 'second', 'password'), map(contents, controls)), seq=seq)
        temp = directory / 'snapshot.tmp'
        temp.write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
        try:
            temp.replace(directory / 'snapshot.json')
        except OSError:
            pass  # Retry next tick if a simultaneous reader has the file open.
    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(40)
    QTimer.singleShot(120_000, app.quit)
    return app.exec()


def run():
    from core import DEFAULT_SETTINGS
    from win_engine import Engine, INPUT, KBD, bind, key_event, user
    bind(user, 'SetForegroundWindow', W.BOOL, W.HWND)
    bind(user, 'AttachThreadInput', W.BOOL, W.DWORD, W.DWORD, W.BOOL)
    bind(user, 'BringWindowToTop', W.BOOL, W.HWND)
    bind(user, 'VkKeyScanW', C.c_short, W.WCHAR)

    class TestEngine(Engine):
        def keyboard(self, code, message, address):
            event = C.cast(address, C.POINTER(KBD)).contents
            if event.dwExtraInfo == TAG:
                local = KBD.from_buffer_copy(event)
                local.flags &= ~0x12
                return super().keyboard(code, message, C.addressof(local))
            return super().keyboard(code, message, address)

    events = []
    data = dict(version=1, settings=copy.deepcopy(DEFAULT_SETTINGS), snippets=[
        dict(id='hi', label='Hi', shortcut=';hi', text='Hello Ω 😀'),
        dict(id='multi', label='Multiline', shortcut=';multi', text='Line one\nLine two'),
        dict(id='upper', label='Uppercase', shortcut=';Hi', text='Upper'),
    ])
    engine = TestEngine(data, lambda *x: events.append(x))
    results = []
    with tempfile.TemporaryDirectory(prefix='twisttype-integration-') as directory:
        directory = Path(directory)
        child = subprocess.Popen([sys.executable, __file__, '--target', str(directory)])
        def read(name):
            try:
                return json.loads((directory / name).read_text(encoding='utf-8'))
            except (OSError, ValueError):
                return {}
        def wait(fn, message):
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                value = fn()
                if value:
                    return value
                time.sleep(.04)
            raise AssertionError(message + ': ' + str(read('snapshot.json')) + ' events=' + str(events))
        seq = 0
        def command(**kwargs):
            nonlocal seq
            seq += 1
            temp = directory / 'command.tmp'
            temp.write_text(json.dumps(dict(seq=seq, **kwargs)))
            temp.replace(directory / 'command.json')
            wait(lambda: read('snapshot.json').get('seq') == seq, 'Target command was not applied')
            hwnd = read('ready.json')['hwnd']
            from win_engine import kernel
            foreground_tid = user.GetWindowThreadProcessId(user.GetForegroundWindow(), None)
            current_tid = kernel.GetCurrentThreadId()
            attached = user.AttachThreadInput(current_tid, foreground_tid, True) if foreground_tid != current_tid else False
            try:
                user.BringWindowToTop(hwnd)
                user.SetForegroundWindow(hwnd)
            finally:
                if attached:
                    user.AttachThreadInput(current_tid, foreground_tid, False)
            wait(lambda: user.GetForegroundWindow() == hwnd, 'Test target did not receive foreground focus')
            if kwargs.get('clear'):
                send(0x24)  # Home resets the typed token after the harness clears a field.
        def send(vk, shift=False, tag=TAG):
            items = []
            if shift:
                items.append(key_event(0x10))
            items.extend((key_event(vk), key_event(vk, flags=2)))
            if shift:
                items.append(key_event(0x10, flags=2))
            for item in items:
                item.ki.dwExtraInfo = tag
            batch = (INPUT * len(items))(*items)
            assert user.SendInput(len(batch), batch, C.sizeof(INPUT)) == len(batch)
            time.sleep(.055)
        def type_text(text):
            for char in text:
                mapped = user.VkKeyScanW(char)
                assert mapped != -1
                send(mapped & 255, bool(mapped & 0x100))
        def check(name, expected, field='first'):
            wait(lambda: read('snapshot.json').get(field) == expected, name)
            results.append(name)
        try:
            wait(lambda: read('ready.json'), 'Target did not open')
            engine.start()
            command(clear=True)
            type_text(';hi ')
            check('Space / Unicode insertion', 'Hello Ω 😀 ')
            command(clear=True)
            type_text(';hi')
            send(9)
            type_text('x')
            check('Tab consumed, focus retained', 'Hello Ω 😀x')
            command(clear=True)
            type_text(';multi ')
            check('Multiline insertion', 'Line one\nLine two ')
            data['settings']['trigger_mode'] = 'immediate'
            engine.configure(data)
            command(clear=True)
            type_text(';hi')
            check('Immediate insertion', 'Hello Ω 😀')
            command(clear=True)
            type_text(';Hi')
            check('Shift and uppercase shortcut', 'Upper')
            data['settings']['trigger_mode'] = 'delimiter'
            engine.configure(data)
            command(clear=True, title='PowerShell — excluded test window')
            type_text(';hi ')
            check('Excluded title passes through', ';hi ')
            command(clear=True)
            type_text('i ')
            check('Exclusion cleared partial buffer', 'i ')
            command(clear=True, focus=2)
            type_text(';hi ')
            check('Classic password field excluded', ';hi ', 'password')
            command(clear=True)
            data['settings']['excluded_processes'].append('python.exe')
            engine.configure(data)
            type_text(';hi ')
            check('Excluded process passes through', ';hi ')
            data['settings']['excluded_processes'].remove('python.exe')
            engine.configure(data)
            engine.pause(True)
            command(clear=True)
            type_text(';hi ')
            check('Pause passes through', ';hi ')
            engine.pause(False)
            command(clear=True)
            type_text(';h')
            command(focus=1)
            type_text('i ')
            check('Focus switch resets token', 'i ', 'second')
            command(clear=True)
            type_text(';hx')
            send(8)
            type_text('i ')
            check('Backspace correction', 'Hello Ω 😀 ')
            command(clear=True)
            type_text(';h')
            send(ord('X'), tag=0)
            type_text('i ')
            check('Untrusted synthetic input resets token', ';hxi ')
            assert not any(kind == 'error' for kind, _ in events), events
            assert engine.running
            results.append('Hooks remain running after exclusions and pause')
        finally:
            engine.stop()
            if child.poll() is None:
                (directory / 'command.json').write_text(json.dumps({'seq': 9999, 'quit': True}))
                try:
                    child.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    child.terminate()
                    child.wait(timeout=4)
    output = {'passed': len(results), 'checks': results, 'expansions': engine.count, 'events': events}
    (ROOT / 'integration-results.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    if '--target' in sys.argv:
        raise SystemExit(target(sys.argv[-1]))
    run()
