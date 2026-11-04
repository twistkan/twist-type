"""Windows low-level hooks and Unicode SendInput; no clipboard, disk key log, or polling loop."""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import logging
import os
import threading

from core import Matcher, excluded

user = C.WinDLL('user32', use_last_error=True)
kernel = C.WinDLL('kernel32', use_last_error=True)
ULONG_PTR = C.c_size_t
LRESULT = C.c_ssize_t
HOOKPROC = C.WINFUNCTYPE(LRESULT, C.c_int, W.WPARAM, W.LPARAM)


class KBD(C.Structure):
    _fields_ = [('vkCode', W.DWORD), ('scanCode', W.DWORD), ('flags', W.DWORD),
                ('time', W.DWORD), ('dwExtraInfo', ULONG_PTR)]


class KEYINPUT(C.Structure):
    _fields_ = [('wVk', W.WORD), ('wScan', W.WORD), ('dwFlags', W.DWORD),
                ('time', W.DWORD), ('dwExtraInfo', ULONG_PTR)]


class MOUSEINPUT(C.Structure):
    _fields_ = [('dx', W.LONG), ('dy', W.LONG), ('mouseData', W.DWORD),
                ('dwFlags', W.DWORD), ('time', W.DWORD), ('dwExtraInfo', ULONG_PTR)]


class INPUTUNION(C.Union):
    _fields_ = [('ki', KEYINPUT), ('mi', MOUSEINPUT)]


class INPUT(C.Structure):
    _anonymous_ = ('u',)
    _fields_ = [('type', W.DWORD), ('u', INPUTUNION)]


class GUIINFO(C.Structure):
    _fields_ = [('cbSize', W.DWORD), ('flags', W.DWORD), ('hwndActive', W.HWND),
                ('hwndFocus', W.HWND), ('hwndCapture', W.HWND), ('hwndMenuOwner', W.HWND),
                ('hwndMoveSize', W.HWND), ('hwndCaret', W.HWND), ('rcCaret', W.RECT)]


def bind(dll, name, restype, *args):
    fn = getattr(dll, name)
    fn.restype, fn.argtypes = restype, list(args)
    return fn


bind(user, 'SetWindowsHookExW', W.HANDLE, C.c_int, HOOKPROC, W.HINSTANCE, W.DWORD)
bind(user, 'CallNextHookEx', LRESULT, W.HANDLE, C.c_int, W.WPARAM, W.LPARAM)
bind(user, 'UnhookWindowsHookEx', W.BOOL, W.HANDLE)
bind(user, 'GetForegroundWindow', W.HWND)
bind(user, 'GetWindowThreadProcessId', W.DWORD, W.HWND, C.POINTER(W.DWORD))
bind(user, 'GetWindowTextW', C.c_int, W.HWND, W.LPWSTR, C.c_int)
bind(user, 'GetClassNameW', C.c_int, W.HWND, W.LPWSTR, C.c_int)
bind(user, 'GetWindowLongW', W.LONG, W.HWND, C.c_int)
bind(user, 'GetGUIThreadInfo', W.BOOL, W.DWORD, C.POINTER(GUIINFO))
bind(user, 'GetAsyncKeyState', C.c_short, C.c_int)
bind(user, 'GetKeyState', C.c_short, C.c_int)
bind(user, 'GetKeyboardLayout', W.HANDLE, W.DWORD)
bind(user, 'ToUnicodeEx', C.c_int, W.UINT, W.UINT, C.POINTER(C.c_ubyte), W.LPWSTR, C.c_int, W.UINT, W.HANDLE)
bind(user, 'SendInput', W.UINT, W.UINT, C.POINTER(INPUT), C.c_int)
bind(user, 'GetMessageW', W.BOOL, C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT)
bind(user, 'PeekMessageW', W.BOOL, C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT, W.UINT)
bind(user, 'PostThreadMessageW', W.BOOL, W.DWORD, W.UINT, W.WPARAM, W.LPARAM)
bind(kernel, 'GetModuleHandleW', W.HMODULE, W.LPCWSTR)
bind(kernel, 'GetCurrentThreadId', W.DWORD)
bind(kernel, 'OpenProcess', W.HANDLE, W.DWORD, W.BOOL, W.DWORD)
bind(kernel, 'CloseHandle', W.BOOL, W.HANDLE)
bind(kernel, 'QueryFullProcessImageNameW', W.BOOL, W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD))


def key_event(vk=0, scan=0, flags=0):
    return INPUT(type=1, u=INPUTUNION(ki=KEYINPUT(vk, scan, flags, 0, 0x54574953)))


def replacement_inputs(count, text):
    events = []
    for _ in range(count):
        events.extend((key_event(8), key_event(8, flags=2)))
    # A single batch preserves order and avoids taking ownership of the clipboard.
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    for char in text:
        if char in '\n\t':
            vk = 13 if char == '\n' else 9
            events.extend((key_event(vk), key_event(vk, flags=2)))
        else:
            encoded = char.encode('utf-16-le')
            for i in range(0, len(encoded), 2):
                unit = int.from_bytes(encoded[i:i+2], 'little')
                events.extend((key_event(scan=unit, flags=4), key_event(scan=unit, flags=6)))
    return (INPUT * len(events))(*events)


class Engine:
    def __init__(self, data, notify=lambda *_: None):
        self.lock = threading.RLock()
        self.matcher = Matcher(data)
        self.settings = data['settings']
        self.paused = False
        self.notify = notify
        self.thread_id = 0
        self.context = None
        self.pid = None
        self.process = ''
        self.ready = threading.Event()
        self.error = None
        self.count = 0
        self.running = False

    def configure(self, data):
        with self.lock:
            self.matcher.configure(data)
            self.settings = data['settings']
            self.context = None

    def pause(self, value):
        with self.lock:
            self.paused = value
            self.matcher.reset()

    def start(self):
        self.thread = threading.Thread(target=self.run, name='TwistType hooks', daemon=True)
        self.thread.start()
        if not self.ready.wait(5):
            raise RuntimeError('Keyboard hook did not start in time.')
        if self.error:
            raise RuntimeError(self.error)

    def stop(self):
        if self.thread_id:
            user.PostThreadMessageW(self.thread_id, 0x12, 0, 0)
            self.thread.join(timeout=3)

    def active(self):
        hwnd = user.GetForegroundWindow()
        if not hwnd:
            return None
        pid = W.DWORD()
        tid = user.GetWindowThreadProcessId(hwnd, C.byref(pid))
        if pid.value == os.getpid():
            return None
        title = C.create_unicode_buffer(1024)
        user.GetWindowTextW(hwnd, title, len(title))
        info = GUIINFO(cbSize=C.sizeof(GUIINFO))
        if not user.GetGUIThreadInfo(tid, C.byref(info)):
            return None
        if pid.value != self.pid:
            self.pid, self.process = pid.value, ''
            handle = kernel.OpenProcess(0x1000, False, pid.value)
            if not handle:
                return None  # Unknown/protected foreground process: fail closed.
            try:
                path, size = C.create_unicode_buffer(32768), W.DWORD(32768)
                if not kernel.QueryFullProcessImageNameW(handle, 0, path, C.byref(size)):
                    self.pid = None
                    return None
                self.process = path.value.rsplit('\\', 1)[-1]
            finally:
                kernel.CloseHandle(handle)
        if not self.process or excluded(title.value, self.process, self.settings):
            return None
        cls = C.create_unicode_buffer(128)
        user.GetClassNameW(info.hwndFocus, cls, len(cls))
        if 'edit' in cls.value.casefold() and user.GetWindowLongW(info.hwndFocus, -16) & 0x20:
            return None  # ES_PASSWORD for classic Windows password fields.
        return hwnd, info.hwndFocus, tid

    def keyboard(self, code, message, address):
        try:
            if code >= 0:
                event = C.cast(address, C.POINTER(KBD)).contents
                if event.flags & 0x12:  # Never expand synthetic input (including our own).
                    if event.dwExtraInfo != 0x54574953:
                        with self.lock:
                            self.matcher.reset()
                    return user.CallNextHookEx(None, code, message, address)
                if message in (0x100, 0x104):
                    with self.lock:
                        active = None if self.paused else self.active()
                        if active is None:
                            self.matcher.reset()
                            self.context = None
                        else:
                            if active != self.context:
                                self.matcher.reset()
                                self.context = active
                            vk = event.vkCode
                            modifiers = any(user.GetAsyncKeyState(k) & 0x8000 for k in (0x11, 0x12, 0x5B, 0x5C))
                            if modifiers or vk in (0x10, 0xA0, 0xA1, 0x14):
                                # Shift alone must not break uppercase shortcuts.
                                if modifiers or vk == 0x14:
                                    self.matcher.reset()
                            else:
                                key = {8: 'BACKSPACE', 9: 'TAB', 32: 'SPACE'}.get(vk)
                                if key is None:
                                    state = (C.c_ubyte * 256)()
                                    for k in (0x10, 0xA0, 0xA1):
                                        if user.GetAsyncKeyState(k) & 0x8000:
                                            state[k] = 0x80
                                    state[0x14] = user.GetKeyState(0x14) & 1
                                    output = C.create_unicode_buffer(8)
                                    n = user.ToUnicodeEx(vk, event.scanCode, state, output, 8, 4, user.GetKeyboardLayout(active[2]))
                                    key = output.value if n == 1 else 'RESET'
                                match = self.matcher.feed(key)
                                if match:
                                    # Check focus again immediately before altering the document.
                                    if self.active() != active:
                                        self.matcher.reset()
                                        return user.CallNextHookEx(None, code, message, address)
                                    events = replacement_inputs(*match)
                                    sent = user.SendInput(len(events), events, C.sizeof(INPUT))
                                    if sent != len(events):
                                        self.paused = True
                                        self.notify('error', 'Windows blocked text insertion. Expansion is paused; use apps running at the same permission level.')
                                    else:
                                        self.count += 1
                                        self.notify('expanded', self.count)
                                    # Consume trigger key; Tab expands without navigating out.
                                    return 1
        except Exception:
            self.matcher.reset()
            self.paused = True
            logging.exception('Expansion paused after a hook error')
            self.notify('error', 'Expansion paused after an internal error. See twisttype.log.')
        return user.CallNextHookEx(None, code, message, address)

    def mouse(self, code, message, address):
        if code >= 0 and message in (0x201, 0x204, 0x207, 0x20A, 0x20E):
            with self.lock:
                self.matcher.reset()
        return user.CallNextHookEx(None, code, message, address)

    def run(self):
        hooks = []
        try:
            self.thread_id = kernel.GetCurrentThreadId()
            msg = W.MSG()
            user.PeekMessageW(C.byref(msg), None, 0, 0, 0)
            self.callbacks = HOOKPROC(self.keyboard), HOOKPROC(self.mouse)
            for kind, callback in zip((13, 14), self.callbacks):
                handle = user.SetWindowsHookExW(kind, callback, kernel.GetModuleHandleW(None), 0)
                if not handle:
                    raise C.WinError(C.get_last_error())
                hooks.append(handle)
            self.running = True
            self.ready.set()
            while True:
                result = user.GetMessageW(C.byref(msg), None, 0, 0)
                if result <= 0:
                    if result == -1:
                        raise C.WinError(C.get_last_error())
                    break
        except Exception as error:
            self.error = str(error)
            self.notify('error', f'Keyboard hook stopped: {error}')
        finally:
            self.running = False
            for handle in hooks:
                user.UnhookWindowsHookEx(handle)
            self.ready.set()
