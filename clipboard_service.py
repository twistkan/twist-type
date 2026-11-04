"""Qt clipboard notifications, native sensitivity metadata, global hotkey, and safe replay."""
import base64
import ctypes as C
from ctypes import wintypes as W
import os
import re
import struct

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QMimeData, QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QWidget

from clipboard_core import MAX_ITEM, PASSWORD_APPS, SECRET_MARKERS
from win_engine import GUIINFO, INPUT, bind, kernel, key_event, user

bind(user, 'RegisterClipboardFormatW', W.UINT, W.LPCWSTR)
bind(user, 'OpenClipboard', W.BOOL, W.HWND)
bind(user, 'CloseClipboard', W.BOOL)
bind(user, 'IsClipboardFormatAvailable', W.BOOL, W.UINT)
bind(user, 'GetClipboardData', W.HANDLE, W.UINT)
bind(user, 'EmptyClipboard', W.BOOL)
bind(user, 'SetClipboardData', W.HANDLE, W.UINT, W.HANDLE)
bind(user, 'GetClipboardOwner', W.HWND)
bind(user, 'GetClipboardSequenceNumber', W.DWORD)
bind(user, 'RegisterHotKey', W.BOOL, W.HWND, C.c_int, W.UINT, W.UINT)
bind(user, 'UnregisterHotKey', W.BOOL, W.HWND, C.c_int)
bind(user, 'SetForegroundWindow', W.BOOL, W.HWND)
bind(user, 'IsWindow', W.BOOL, W.HWND)
bind(user, 'IsChild', W.BOOL, W.HWND, W.HWND)
bind(user, 'SetFocus', W.HWND, W.HWND)
bind(user, 'AttachThreadInput', W.BOOL, W.DWORD, W.DWORD, W.BOOL)
bind(kernel, 'GlobalLock', C.c_void_p, W.HANDLE)
bind(kernel, 'GlobalUnlock', W.BOOL, W.HANDLE)
bind(kernel, 'GlobalSize', C.c_size_t, W.HANDLE)
bind(kernel, 'GlobalAlloc', W.HANDLE, W.UINT, C.c_size_t)
bind(kernel, 'GlobalFree', W.HANDLE, W.HANDLE)

HOTKEYS = {'Ctrl+Alt+V': (0x4003, 0x56), 'Ctrl+Alt+Shift+V': (0x4007, 0x56)}


class ClipboardBusy(OSError):
    pass


def write_clipboard(hwnd, formats):
    """Use owned HGLOBAL data, avoiding OLE's delayed-rendering lifetime races."""
    handles = []
    try:
        for ident, data in formats:
            handle = kernel.GlobalAlloc(0x42, len(data))
            pointer = kernel.GlobalLock(handle) if handle else None
            if not pointer:
                if handle:
                    kernel.GlobalFree(handle)
                raise OSError('Could not allocate clipboard data.')
            C.memmove(pointer, data, len(data))
            kernel.GlobalUnlock(handle)
            handles.append([ident, handle])
        if not user.OpenClipboard(hwnd):
            raise ClipboardBusy('The clipboard is busy. Try again.')
        try:
            if not user.EmptyClipboard():
                raise OSError('Could not update the clipboard.')
            for entry in handles:
                if not user.SetClipboardData(entry[0], entry[1]):
                    raise OSError('Could not restore the clipboard item.')
                entry[1] = None  # Windows now owns this HGLOBAL.
        finally:
            user.CloseClipboard()
    finally:
        for _, handle in handles:
            if handle:
                kernel.GlobalFree(handle)


def clipboard_metadata():
    """Read only metadata first. None means clipboard is temporarily busy."""
    if not user.OpenClipboard(None):
        return None
    try:
        for name in SECRET_MARKERS:
            if user.IsClipboardFormatAvailable(user.RegisterClipboardFormatW(name)):
                return True
        ident = user.RegisterClipboardFormatW('CanIncludeInClipboardHistory')
        if user.IsClipboardFormatAvailable(ident):
            handle = user.GetClipboardData(ident)
            pointer = kernel.GlobalLock(handle) if handle else None
            try:
                if not pointer or kernel.GlobalSize(handle) < 4 or C.c_uint32.from_address(pointer).value == 0:
                    return True
            finally:
                if pointer:
                    kernel.GlobalUnlock(handle)
        return False
    finally:
        user.CloseClipboard()


def source_context():
    owner = user.GetClipboardOwner()
    if not owner:
        return None
    pid = W.DWORD()
    user.GetWindowThreadProcessId(owner, C.byref(pid))
    handle = kernel.OpenProcess(0x1000, False, pid.value)
    if not handle:
        return None
    try:
        name, length = C.create_unicode_buffer(32768), W.DWORD(32768)
        if not kernel.QueryFullProcessImageNameW(handle, 0, name, C.byref(length)):
            return None
        process = name.value.rsplit('\\', 1)[-1]
    finally:
        kernel.CloseHandle(handle)
    if process.casefold() in PASSWORD_APPS:
        return None
    foreground = user.GetForegroundWindow()
    front_pid = W.DWORD()
    thread = user.GetWindowThreadProcessId(foreground, C.byref(front_pid))
    if front_pid.value == pid.value:
        title = C.create_unicode_buffer(1024)
        user.GetWindowTextW(foreground, title, len(title))
        if re.search(r'(?i)password|passphrase|keepass|bitwarden|1password|proton.?pass|lastpass|dashlane|sign[ -]?in|log[ -]?in', title.value):
            return None
        info = GUIINFO(cbSize=C.sizeof(GUIINFO))
        if not user.GetGUIThreadInfo(thread, C.byref(info)):
            return None
        cls = C.create_unicode_buffer(128)
        user.GetClassNameW(info.hwndFocus, cls, len(cls))
        if 'edit' in cls.value.casefold() and user.GetWindowLongW(info.hwndFocus, -16) & 0x20:
            return None
    return process


class HotkeyWindow(QWidget):
    activated = Signal()

    def __init__(self):
        super().__init__()
        self.registered = False

    def register(self, name):
        if self.registered:
            user.UnregisterHotKey(int(self.winId()), 71)
        modifiers, key = HOTKEYS[name]
        self.registered = bool(user.RegisterHotKey(int(self.winId()), 71, modifiers, key))
        return self.registered

    def nativeEvent(self, event_type, message):
        event = W.MSG.from_address(int(message))
        if event.message == 0x312 and event.wParam == 71:
            self.activated.emit()
            return True, 0
        return False, 0

    def stop(self):
        if self.registered:
            user.UnregisterHotKey(int(self.winId()), 71)
            self.registered = False


class ClipboardService(QObject):
    changed = Signal()
    attention = Signal(str)
    quick_access = Signal()

    def __init__(self, history, settings):
        super().__init__()
        self.history = history
        self.settings = settings
        self.clipboard = QApplication.clipboard()
        self.started = False
        self.suspended = False
        self.skipped = 0
        self.copy_generation = 0
        self.status = history.error or 'Ready to remember new copies.'
        self.hotkeys = HotkeyWindow()
        self.hotkeys.activated.connect(self.quick_access.emit)
        self.flush_timer = QTimer(self)
        self.flush_timer.setSingleShot(True)
        self.flush_timer.timeout.connect(self.flush)

    def start(self):
        self.sequence = user.GetClipboardSequenceNumber()  # Do not import pre-existing clipboard contents.
        self.clipboard.dataChanged.connect(self.schedule_capture)
        self.started = True
        self.configure(self.settings)

    def configure(self, settings):
        self.settings = settings
        self.history.configure(settings['clipboard_limit'], settings['clipboard_strict'])
        if self.started and not self.hotkeys.register(settings['clipboard_hotkey']):
            self.status = 'Clipboard shortcut is in use. Choose the alternate shortcut in Settings.'
            self.attention.emit(self.status)
        if self.history.path and not self.history.error and self.started:
            self.flush_timer.start(150)
        self.changed.emit()

    def flush(self):
        try:
            self.history.save()
        except Exception:
            self.status = 'Clipboard history could not be saved securely. Recording is paused.'
            self.suspended = True
            self.attention.emit(self.status)
        self.changed.emit()

    def schedule_capture(self):
        # QClipboard may emit dataChanged from inside its own OLE write. Never
        # open/close the native clipboard recursively from that notification.
        QTimer.singleShot(0, self.capture)

    def capture(self, attempt=0, expected=None):
        if not self.started:
            return
        sequence = user.GetClipboardSequenceNumber()
        if expected is not None and sequence != expected:
            return
        if attempt == 0:
            if sequence == self.sequence:
                return
            self.sequence = sequence
        if not self.settings['clipboard_enabled'] or self.suspended or self.history.error:
            return
        try:
            protected = clipboard_metadata()
            if protected is None:
                if attempt < 4:
                    QTimer.singleShot(35, lambda: self.capture(attempt + 1, sequence))
                return
            process = None if protected else source_context()
            if not process:
                self.skipped += 1
                self.status = 'Sensitive or unidentified copy omitted.'
                self.changed.emit()
                return
            mime = self.clipboard.mimeData()
            if not mime or any(mime.hasFormat(name) for name in SECRET_MARKERS):
                return
            if mime.hasUrls() and mime.urls() and all(url.isLocalFile() for url in mime.urls()):
                kind, value = 'files', [url.toLocalFile() for url in mime.urls()]
            elif mime.hasImage():
                image = QImage(mime.imageData())
                if image.isNull() or image.width() * image.height() > 16_000_000:
                    return
                data = QByteArray()
                buffer = QBuffer(data)
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                image.save(buffer, 'PNG')
                if data.size() > MAX_ITEM:
                    self.status = 'Image exceeds the 1 MB history limit.'
                    self.changed.emit()
                    return
                kind, value = 'image', base64.b64encode(bytes(data)).decode('ascii')
            elif mime.hasText():
                kind, value = 'text', mime.text()
                if not value.strip() or len(value.encode('utf-8')) > MAX_ITEM:
                    return
            else:
                return
            if user.GetClipboardSequenceNumber() != sequence:
                QTimer.singleShot(0, self.capture)
                return
            if self.history.add(kind, value, process):
                self.status = 'Saved locally with Windows account encryption.'
                self.flush_timer.start(150)
            else:
                self.skipped += 1
                self.status = 'Potentially sensitive copy omitted.'
            self.changed.emit()
        except Exception:
            # Never include clipboard contents in a log or error message.
            self.status = 'This copy could not be captured safely.'
            self.changed.emit()

    def copy_item(self, item, on_ready=None):
        self.copy_generation += 1
        generation = self.copy_generation
        formats = []
        if item['kind'] == 'text':
            formats.append((13, (item['value'] + '\0').encode('utf-16-le')))
        elif item['kind'] == 'files':
            paths = '\0'.join(path.replace('/', '\\') for path in item['value']) + '\0\0'
            formats.append((15, struct.pack('<IiiII', 20, 0, 0, 0, 1) + paths.encode('utf-16-le')))
            formats.append((user.RegisterClipboardFormatW('Preferred DropEffect'), struct.pack('<I', 1)))
        else:
            png = base64.b64decode(item['value'])
            image = QImage.fromData(png, 'PNG')
            if image.isNull():
                raise ValueError('This image cannot be opened.')
            data = QByteArray()
            buffer = QBuffer(data)
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            if not image.save(buffer, 'BMP'):
                raise ValueError('This image cannot be restored.')
            formats.append((8, bytes(data)[14:]))
            formats.append((user.RegisterClipboardFormatW('PNG'), png))
        # Replayed history should not escape into Windows/cloud history or
        # be captured again as a new entry by our listener.
        for name in ('ExcludeClipboardContentFromMonitorProcessing', 'CanUploadToCloudClipboard'):
            value = b'\x01' if name.startswith('Exclude') else b'\x00\x00\x00\x00'
            formats.insert(0, (user.RegisterClipboardFormatW(name), value))
        def attempt(number=0):
            if generation != self.copy_generation:
                return
            try:
                write_clipboard(int(self.hotkeys.winId()), formats)
            except ClipboardBusy:
                if number < 30:
                    QTimer.singleShot(50, lambda: attempt(number + 1))
                    return
                self.status = 'The clipboard is busy. Select the item again to retry.'
                self.attention.emit(self.status)
            except OSError:
                self.status = 'The clipboard item could not be restored.'
                self.attention.emit(self.status)
            else:
                self.status = 'Copied. Paste it wherever you need it.'
                if on_ready:
                    on_ready()
            self.changed.emit()
        attempt()

    def stop(self):
        self.copy_generation += 1
        if self.started:
            self.clipboard.dataChanged.disconnect(self.schedule_capture)
            self.started = False
        self.hotkeys.stop()
        if self.flush_timer.isActive():
            self.flush_timer.stop()
            self.flush()


def paste_to(target):
    """Paste only if the original window and focus field can be restored."""
    hwnd, focus, expected_pid = target
    pid = W.DWORD()
    thread = user.GetWindowThreadProcessId(hwnd, C.byref(pid))
    if (pid.value != expected_pid or not user.IsWindow(hwnd) or not user.IsWindow(focus)
            or (focus != hwnd and not user.IsChild(hwnd, focus))):
        return False
    if any(user.GetAsyncKeyState(k) & 0x8000 for k in (0x10, 0x11, 0x12, 0x5B, 0x5C)):
        return False
    user.SetForegroundWindow(hwnd)
    if user.GetForegroundWindow() != hwnd:
        return False
    info = GUIINFO(cbSize=C.sizeof(GUIINFO))
    if not user.GetGUIThreadInfo(thread, C.byref(info)):
        return False
    if info.hwndFocus != focus:
        current = kernel.GetCurrentThreadId()
        attached = user.AttachThreadInput(current, thread, True) if current != thread else False
        try:
            if current != thread and not attached:
                return False
            user.SetFocus(focus)
        finally:
            if attached:
                user.AttachThreadInput(current, thread, False)
        if not user.GetGUIThreadInfo(thread, C.byref(info)) or info.hwndFocus != focus:
            return False
    events = (INPUT * 4)(key_event(0x11), key_event(0x56), key_event(0x56, flags=2), key_event(0x11, flags=2))
    return user.SendInput(4, events, C.sizeof(INPUT)) == 4


def foreground_target():
    hwnd = user.GetForegroundWindow()
    pid = W.DWORD()
    thread = user.GetWindowThreadProcessId(hwnd, C.byref(pid))
    info = GUIINFO(cbSize=C.sizeof(GUIINFO))
    if pid.value == os.getpid() or not user.GetGUIThreadInfo(thread, C.byref(info)):
        return None
    return hwnd, info.hwndFocus, pid.value
