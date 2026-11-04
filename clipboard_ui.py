"""Clipboard history screen and keyboard-driven picker."""
import base64

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget)

from clipboard_core import preview
from clipboard_service import foreground_target, paste_to


def caption(text, role='muted'):
    label = QLabel(text)
    label.setObjectName(role)
    label.setWordWrap(True)
    return label


def metric(title, value, role='statBlue'):
    frame = QFrame()
    frame.setObjectName(role)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 14, 18, 14)
    layout.addWidget(caption(title))
    number = caption(value, 'metric')
    layout.addWidget(number)
    return frame, number


def add_entries(widget, entries, query=''):
    widget.clear()
    for entry in entries:
        text = preview(entry)
        if query.casefold() not in (text + ' ' + entry['source'] + (' ' + entry['value'] if entry['kind'] == 'text' else '')).casefold():
            continue
        item = QListWidgetItem(f"{text}\n{entry['kind'].capitalize()}  ·  {entry['source']}")
        item.setData(Qt.ItemDataRole.UserRole, entry['id'])
        if entry['kind'] == 'image':
            image = QImage.fromData(base64.b64decode(entry['value']), 'PNG')
            if not image.isNull():
                item.setIcon(QIcon(QPixmap.fromImage(image)))
        widget.addItem(item)


class ClipboardPanel(QWidget):
    def __init__(self, service):
        super().__init__()
        self.service = service
        self.history = service.history
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        row = QHBoxLayout()
        first, self.count = metric('RECENT COPIES', '0 / 20')
        second, self.protection = metric('PASSWORD PROTECTION', 'On', 'statPeach')
        third, self.hotkey = metric('QUICK ACCESS', 'Ctrl+Alt+V', 'statMint')
        for frame in (first, second, third):
            row.addWidget(frame)
        layout.addLayout(row)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search clipboard history…')
        self.search.setAccessibleName('Search clipboard history')
        self.search.textChanged.connect(self.refresh)
        layout.addWidget(self.search)
        split = QSplitter()
        self.list = QListWidget()
        self.list.setAccessibleName('Recent clipboard items')
        self.list.currentItemChanged.connect(self.select)
        split.addWidget(self.list)
        card = QFrame()
        card.setObjectName('card')
        details = QVBoxLayout(card)
        details.setContentsMargins(20, 18, 20, 18)
        details.addWidget(caption('Clipboard preview', 'heading'))
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setAccessibleName('Clipboard item preview')
        self.preview.setPlaceholderText('New copies will appear here. Select one to preview it.')
        details.addWidget(self.preview, 1)
        self.image = QLabel()
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.hide()
        details.addWidget(self.image, 1)
        self.copy_button = QPushButton('Copy selected item')
        self.copy_button.setObjectName('primary')
        self.copy_button.clicked.connect(self.copy_selected)
        details.addWidget(self.copy_button)
        self.remove_button = QPushButton('Remove item')
        self.remove_button.clicked.connect(self.remove_selected)
        details.addWidget(self.remove_button)
        split.addWidget(card)
        split.setSizes([440, 460])
        layout.addWidget(split, 1)
        self.status = caption('')
        layout.addWidget(self.status)
        tools = QHBoxLayout()
        self.pause = QPushButton('Pause recording')
        self.pause.clicked.connect(self.toggle_pause)
        tools.addWidget(self.pause)
        clear = QPushButton('Clear clipboard history')
        clear.setObjectName('danger')
        clear.clicked.connect(self.clear)
        tools.addWidget(clear)
        tools.addStretch()
        layout.addLayout(tools)
        layout.addWidget(caption('Sensitive copies are omitted, not masked. Single-word copies are hidden by default. No detector can recognize every password in ordinary text or images.'))
        service.changed.connect(self.refresh)
        self.refresh()

    def selected(self):
        current = self.list.currentItem()
        ident = current.data(Qt.ItemDataRole.UserRole) if current else None
        return next((item for item in self.history.items if item['id'] == ident), None)

    def refresh(self, *_):
        selected = self.selected()
        ident = selected['id'] if selected else None
        self.list.blockSignals(True)
        add_entries(self.list, self.history.items, self.search.text())
        self.list.blockSignals(False)
        row = next((i for i in range(self.list.count()) if self.list.item(i).data(Qt.ItemDataRole.UserRole) == ident), 0)
        self.list.setCurrentRow(row)
        self.select()
        self.count.setText(f'{len(self.history.items)} / {self.history.limit}')
        self.hotkey.setText(self.service.settings['clipboard_hotkey'])
        paused = self.service.suspended or not self.service.settings['clipboard_enabled']
        self.pause.setText('Resume recording' if self.service.suspended else 'Pause recording')
        self.pause.setEnabled(self.service.settings['clipboard_enabled'] and not self.history.error)
        self.protection.setText('Recording paused' if paused else 'On')
        self.status.setText(self.history.error or self.service.status)

    def select(self, *_):
        item = self.selected()
        self.copy_button.setEnabled(item is not None)
        self.remove_button.setEnabled(item is not None)
        self.preview.setVisible(item is None or item['kind'] != 'image')
        self.image.setVisible(item is not None and item['kind'] == 'image')
        if not item:
            self.preview.clear()
        elif item['kind'] == 'image':
            image = QImage.fromData(base64.b64decode(item['value']), 'PNG')
            self.image.setPixmap(QPixmap.fromImage(image).scaled(380, 280, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.preview.setPlainText(item['value'] if item['kind'] == 'text' else '\n'.join(item['value']))

    def copy_selected(self):
        if item := self.selected():
            try:
                self.service.copy_item(item)
            except Exception:
                QMessageBox.warning(self, 'Could not copy', 'This clipboard item could not be restored.')

    def remove_selected(self):
        if item := self.selected():
            try:
                self.history.remove(item['id'])
                self.service.changed.emit()
            except Exception:
                QMessageBox.warning(self, 'Could not remove', 'The encrypted history file could not be updated.')

    def clear(self):
        if QMessageBox.question(self, 'Clear clipboard history', 'Remove every saved clipboard-history entry? This leaves the current Windows clipboard alone.', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.history.clear()
            self.service.status = 'Clipboard history cleared.'
            self.service.changed.emit()
        except Exception:
            QMessageBox.warning(self, 'Could not clear history', 'The encrypted history file could not be updated.')

    def toggle_pause(self):
        self.service.suspended = not self.service.suspended
        self.service.status = 'Recording paused.' if self.service.suspended else 'Recording resumed.'
        self.service.changed.emit()


class ClipboardPicker(QDialog):
    def __init__(self, service):
        super().__init__()
        self.service = service
        self.target = None
        self.setWindowTitle('TwistType — Quick clipboard')
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.resize(660, 470)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.addWidget(caption('Your recent copies', 'heading'))
        layout.addWidget(caption('Search, choose an item, then press Enter to paste. Esc closes.'))
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search clipboard…')
        self.search.setAccessibleName('Search quick clipboard')
        self.search.textChanged.connect(self.refresh)
        self.search.returnPressed.connect(self.choose)
        self.search.installEventFilter(self)
        layout.addWidget(self.search)
        self.list = QListWidget()
        self.list.setAccessibleName('Quick clipboard items')
        self.list.itemActivated.connect(self.choose)
        layout.addWidget(self.list, 1)
        self.empty = caption('Copy text, an image, or files to start. Protected copies are omitted.')
        layout.addWidget(self.empty)
        paste = QPushButton('Paste selected item')
        paste.setObjectName('primary')
        paste.clicked.connect(self.choose)
        layout.addWidget(paste)
        service.changed.connect(self.refresh)

    def eventFilter(self, watched, event):
        if watched == self.search and event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            delta = 1 if event.key() == Qt.Key.Key_Down else -1
            self.list.setCurrentRow(max(0, min(self.list.count() - 1, self.list.currentRow() + delta)))
            return True
        return super().eventFilter(watched, event)

    def open_picker(self):
        if self.isVisible():
            self.hide()
            return
        self.target = foreground_target()
        self.search.clear()
        self.refresh()
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.search.setFocus()

    def refresh(self, *_):
        add_entries(self.list, self.service.history.items, self.search.text())
        self.list.setCurrentRow(0)
        self.empty.setVisible(self.list.count() == 0)

    def choose(self, *_):
        current = self.list.currentItem()
        if not current:
            return
        item = next((i for i in self.service.history.items if i['id'] == current.data(Qt.ItemDataRole.UserRole)), None)
        if not item:
            return
        target = self.target
        def copied():
            if target:
                def restore():
                    if not paste_to(target):
                        self.service.status = 'Copied. Focus could not be restored safely; press Ctrl+V in the desired field.'
                        self.service.changed.emit()
                QTimer.singleShot(160, restore)
        try:
            self.service.copy_item(item, on_ready=copied)
        except Exception:
            return
        self.hide()
