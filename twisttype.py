"""TwistType 1.0 — personal, offline Windows text expansion."""
from __future__ import annotations

import argparse
import copy
import ctypes
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import uuid

from PySide6.QtCore import QObject, QTimer, Qt, Signal, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QSystemTrayIcon, QTabWidget,
    QVBoxLayout, QWidget, QScrollArea)

from core import Store, data_dir, resource_path
from theme import TOKENS, apply_theme, configure_combo_popup, stylesheet
from clipboard_core import HistoryStore, preview as clipboard_preview
from clipboard_service import ClipboardService
from clipboard_ui import ClipboardPanel, ClipboardPicker, metric
import startup
from win_engine import Engine, kernel

VERSION = '1.1.1'


class Events(QObject):
    event = Signal(str, object)


def button(text, fn, role=''):
    result = QPushButton(text)
    result.setObjectName(role)
    result.clicked.connect(fn)
    return result


def label(text, role=''):
    result = QLabel(text)
    result.setObjectName(role)
    result.setWordWrap(True)
    return result


class Window(QMainWindow):
    def __init__(self, store, engine, events, clipboard_service=None):
        super().__init__()
        self.store, self.engine = store, engine
        self.clipboard_service = clipboard_service or ClipboardService(HistoryStore(), store.data['settings'])
        self.loaded = None
        self.original = ('', '', '')
        self.quitting = False
        self.setWindowTitle(f'TwistType {VERSION} — Snippet Library')
        self.setWindowIcon(QIcon(str(resource_path('assets/twisttype.ico'))))
        self.resize(1240, 840)
        self.setMinimumSize(1040, 720)
        root = QWidget()
        self.setCentralWidget(root)
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(216)
        rail = QVBoxLayout(sidebar)
        rail.setContentsMargins(16, 24, 16, 20)
        mark = QLabel()
        mark.setPixmap(self.windowIcon().pixmap(46, 46))
        rail.addWidget(mark)
        rail.addWidget(label('TwistType', 'brand'))
        rail.addWidget(label('PERSONAL WORKSPACE', 'eyebrow'))
        rail.addSpacing(28)
        self.navigation = QListWidget()
        self.navigation.setObjectName('navigation')
        self.navigation.setAccessibleName('Workspace navigation')
        self.navigation.addItems(['Snippet library', 'Clipboard history', 'Settings', 'Help & privacy'])
        self.navigation.currentRowChanged.connect(lambda row: self.tabs.setCurrentIndex([0, 3, 1, 2][row]) if row >= 0 else None)
        rail.addWidget(self.navigation, 1)
        rail.addWidget(label('LOCAL • OFFLINE', 'eyebrow'))
        rail.addWidget(label(f'Version {VERSION}', 'muted'))
        rail.addWidget(button('Quit TwistType', self.quit))
        shell.addWidget(sidebar)
        content = QWidget()
        shell.addWidget(content, 1)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(16)
        header = QHBoxLayout()
        title = QVBoxLayout()
        self.page_title = label('Snippet library', 'brand')
        title.addWidget(self.page_title)
        tagline = label('A little less typing. A little more time.', 'muted')
        tagline.setWordWrap(False)
        title.addWidget(tagline)
        header.addLayout(title, 1)
        header.addStretch()
        self.clipboard_button = button('Clipboard  ·  Ctrl+Alt+V', self.open_clipboard)
        header.addWidget(self.clipboard_button)
        self.pause_button = button('Pause expansion', self.toggle_pause)
        header.addWidget(self.pause_button)
        layout.addLayout(header)
        self.tabs = QTabWidget()
        self.tabs.tabBar().hide()
        self.tabs.currentChanged.connect(self.sync_navigation)
        layout.addWidget(self.tabs)
        self.build_library()
        self.build_settings()
        self.build_about()
        self.clipboard_panel = ClipboardPanel(self.clipboard_service)
        self.tabs.addTab(self.clipboard_panel, 'Clipboard history')
        self.picker = ClipboardPicker(self.clipboard_service)
        self.clipboard_service.quick_access.connect(self.picker.open_picker)
        self.clipboard_service.attention.connect(lambda message: self.statusBar().showMessage(message, 12000))
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        menu = QMenu()
        menu.addAction('Open TwistType', self.show_editor)
        self.pause_action = menu.addAction('Pause expansion', self.toggle_pause)
        menu.addAction('Clipboard history', self.open_clipboard)
        self.recent_menu = menu.addMenu('Recent clipboard items')
        self.recent_menu.aboutToShow.connect(self.populate_recent_menu)
        menu.addAction('Reload snippets from disk', self.reload)
        menu.addSeparator()
        menu.addAction('Quit TwistType', self.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_editor() if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
        self.events = events
        events.event.connect(self.on_event)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(1000)
        QShortcut(QKeySequence.StandardKey.Save, self, activated=self.save_snippet)
        QShortcut(QKeySequence.StandardKey.New, self, activated=self.new_snippet)
        QShortcut(QKeySequence('Ctrl+Q'), self, activated=self.quit)
        self.navigation.setCurrentRow(0)
        self.populate()
        if self.store.data['snippets']:
            self.list.setCurrentRow(0)
        else:
            self.new_snippet()
        self.refresh_status()

    def sync_navigation(self, index):
        mapping = {0: 0, 3: 1, 1: 2, 2: 3}
        if index not in mapping:
            return
        self.navigation.blockSignals(True)
        self.navigation.setCurrentRow(mapping[index])
        self.navigation.blockSignals(False)
        self.page_title.setText(['Snippet library', 'Settings', 'Help & privacy', 'Clipboard history'][index])

    def open_clipboard(self):
        self.tabs.setCurrentIndex(3)
        self.show_editor()

    def populate_recent_menu(self):
        self.recent_menu.clear()
        entries = self.clipboard_service.history.items[:10]
        if not entries:
            action = self.recent_menu.addAction('No saved copies yet')
            action.setEnabled(False)
        for entry in entries:
            action = self.recent_menu.addAction(clipboard_preview(entry).replace('&', '&&')[:80])
            action.triggered.connect(lambda _checked=False, item=entry: self.clipboard_service.copy_item(item))

    def build_library(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        stats = QHBoxLayout()
        first, self.snippet_count = metric('YOUR SNIPPETS', str(len(self.store.data['snippets'])))
        second, self.trigger_summary = metric('EXPAND WITH', 'Space / Tab', 'statPeach')
        stats.addWidget(first)
        stats.addWidget(second)
        outer.addLayout(stats)
        split = QSplitter()
        outer.addWidget(split)
        side = QWidget()
        left = QVBoxLayout(side)
        left.setContentsMargins(0, 0, 16, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search names, shortcuts, or text')
        self.search.setAccessibleName('Search snippets')
        self.search.textChanged.connect(self.populate)
        left.addWidget(self.search)
        self.list = QListWidget()
        self.list.setAccessibleName('Snippet library')
        self.list.currentItemChanged.connect(self.select)
        left.addWidget(self.list)
        left.addWidget(button('+  New snippet', self.new_snippet, 'primary'))
        tools = QHBoxLayout()
        tools.addWidget(button('Import', self.import_file))
        tools.addWidget(button('Export', self.export_file))
        left.addLayout(tools)
        split.addWidget(side)
        card = QFrame()
        card.setObjectName('card')
        edit = QVBoxLayout(card)
        edit.setContentsMargins(24, 22, 24, 22)
        edit.setSpacing(TOKENS['space'])
        edit.addWidget(label('Make it yours', 'heading'))
        name_label = label('Name')
        edit.addWidget(name_label)
        self.name = QLineEdit()
        self.name.setPlaceholderText('e.g. Email signature')
        name_label.setBuddy(self.name)
        edit.addWidget(self.name)
        shortcut_label = label('Shortcut')
        edit.addWidget(shortcut_label)
        self.shortcut = QLineEdit()
        self.shortcut.setPlaceholderText(';signature')
        shortcut_label.setBuddy(self.shortcut)
        edit.addWidget(self.shortcut)
        edit.addWidget(label('Start with ; : / ! . or ,  •  Case-sensitive  •  No spaces', 'muted'))
        text_label = label('Expanded text')
        edit.addWidget(text_label)
        self.text = QPlainTextEdit()
        self.text.setPlaceholderText('Write the text you want to insert…')
        text_label.setBuddy(self.text)
        edit.addWidget(self.text, 1)
        self.hint = label('', 'muted')
        edit.addWidget(self.hint)
        actions = QHBoxLayout()
        self.delete_button = button('Delete', self.delete_snippet, 'danger')
        actions.addWidget(self.delete_button)
        actions.addStretch()
        actions.addWidget(button('Save snippet  ·  Ctrl+S', self.save_snippet, 'primary'))
        edit.addLayout(actions)
        split.addWidget(card)
        split.setSizes([340, 660])
        self.tabs.addTab(page, 'Snippet library')
        for field in (self.name, self.shortcut, self.text):
            field.textChanged.connect(self.update_hint)

    def build_settings(self):
        page = QWidget()
        form = QVBoxLayout(page)
        form.setSpacing(12)
        form.addWidget(label('How TwistType works', 'heading'))
        form.addWidget(label('Expand shortcuts', 'muted'))
        self.mode = QComboBox()
        configure_combo_popup(self.mode)
        self.mode.addItem('After Space or Tab (recommended)', 'delimiter')
        self.mode.addItem('Immediately after the shortcut', 'immediate')
        self.mode.setAccessibleName('Expansion trigger')
        form.addWidget(self.mode)
        self.keep_space = QCheckBox('Keep the space after expanding (Tab is consumed)')
        form.addWidget(self.keep_space)
        form.addWidget(label('Extra excluded window titles — one phrase per line', 'muted'))
        self.titles = QPlainTextEdit()
        self.titles.setAccessibleName('Excluded window titles')
        self.titles.setMaximumHeight(100)
        form.addWidget(self.titles)
        form.addWidget(label('Extra excluded processes — one executable name per line', 'muted'))
        self.processes = QPlainTextEdit()
        self.processes.setAccessibleName('Excluded processes')
        self.processes.setMaximumHeight(100)
        form.addWidget(self.processes)
        form.addWidget(label('Terminal, PowerShell, Command Prompt, KeePass, and the bundled password-manager exclusions always apply.', 'muted'))
        form.addWidget(button('Apply expansion settings', self.save_settings, 'primary'), alignment=Qt.AlignmentFlag.AlignLeft)
        self.startup_check = QCheckBox('Start TwistType when I sign in to Windows')
        self.startup_check.setChecked(startup.enabled())
        self.startup_check.clicked.connect(self.change_startup)
        form.addWidget(self.startup_check)
        form.addWidget(label('Startup is optional. Closing this window keeps TwistType in the tray.', 'muted'))
        form.addSpacing(16)
        form.addWidget(label('Clipboard history', 'heading'))
        self.clip_enabled = QCheckBox('Remember new clipboard copies locally')
        form.addWidget(self.clip_enabled)
        self.clip_strict = QCheckBox('Hide single-word copies too (safer for passwords)')
        form.addWidget(self.clip_strict)
        form.addWidget(label('History capacity', 'muted'))
        self.clip_limit = QComboBox()
        configure_combo_popup(self.clip_limit)
        for count in (10, 20, 50):
            self.clip_limit.addItem(f'{count} recent items', count)
        form.addWidget(self.clip_limit)
        form.addWidget(label('Global clipboard shortcut', 'muted'))
        self.clip_hotkey = QComboBox()
        configure_combo_popup(self.clip_hotkey)
        self.clip_hotkey.addItems(['Ctrl+Alt+V', 'Ctrl+Alt+Shift+V'])
        form.addWidget(self.clip_hotkey)
        form.addWidget(label('Password-manager copies, protected clipboard formats, known secret patterns, and identifiable password fields are always omitted. Ordinary text and images can contain undetectable passwords; pause recording for sensitive copying.', 'muted'))
        form.addWidget(button('Apply clipboard settings', self.save_clipboard_settings, 'primary'), alignment=Qt.AlignmentFlag.AlignLeft)
        form.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        self.tabs.addTab(scroll, 'Settings')
        self.load_settings()

    def build_about(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setSpacing(16)
        box.addWidget(label('Small shortcuts. More time back.', 'heading'))
        box.addWidget(label(f'TwistType {VERSION}  •  Personal offline edition', 'muted'))
        box.addWidget(label('1. Create a snippet and save it.\n2. Open Notepad, Word, or another text app.\n3. Type its shortcut, then press Space or Tab.'))
        box.addWidget(label('Space can be preserved; Tab triggers expansion without moving to the next field. Immediate mode is available in Settings. Shortcuts must occupy a whole typed token. Move the cursor or click to start fresh.'))
        box.addWidget(label('Your data stays in %LOCALAPPDATA%\\TwistType. The app creates snippets.yaml automatically on first launch. Saves keep one previous version in snippets.yaml.bak. No account, cloud sync, or analytics. Clipboard history is saved separately with Windows account encryption.'))
        box.addWidget(label('Press Ctrl+Alt+V anywhere for clipboard history. Search or use the arrow keys, then Enter to paste the selected item into the previous app. In the clipboard screen, Copy selected item restores it for manual pasting. Text, images up to 1 MB, and copied file paths are supported; file contents are never duplicated. The latest 20 distinct copies are kept by default.'))
        box.addWidget(label('Clipboard password protection omits password-manager copies, source-app sensitivity markers, identifiable password fields, and likely secrets. Single-word copies are hidden by default. No automatic detector can recognize every password in unmarked text or images; pause recording for sensitive work. Clear history deletes the stored entries.'))
        box.addWidget(label('Use normal, non-administrator apps. Elevated apps may block text insertion. Classic Windows password fields are skipped; browser/custom password fields cannot always be recognized. Add sensitive apps or window titles to exclusions. Unicode and multiline insertion depend on the receiving app. IME composition is not supported for shortcut entry.'))
        box.addWidget(label('This editor is excluded from expansion. Test snippets in another app.', 'muted'))
        box.addWidget(label('Known limit: some Qt text editors can reorder emoji mixed with other text. Use plain text without emoji in those apps.', 'muted'))
        box.addWidget(button('Open local data folder', lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.path.parent)))), alignment=Qt.AlignmentFlag.AlignLeft)
        box.addWidget(button('Open third-party notices', lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(resource_path('THIRD-PARTY.md'))))), alignment=Qt.AlignmentFlag.AlignLeft)
        box.addWidget(button('Reload snippets from disk', self.reload), alignment=Qt.AlignmentFlag.AlignLeft)
        box.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        self.tabs.addTab(scroll, 'Help && privacy')

    def values(self):
        return self.name.text(), self.shortcut.text(), self.text.toPlainText()

    def dirty(self):
        return self.values() != self.original

    def update_hint(self):
        self.hint.setText(f'{len(self.text.toPlainText()):,} characters' + ('  •  Unsaved changes' if self.dirty() else '  •  Saved locally'))

    def confirm_changes(self):
        if not self.dirty():
            return True
        answer = QMessageBox.question(self, 'Unsaved snippet', 'Save your snippet before continuing?',
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        return self.save_snippet() if answer == QMessageBox.StandardButton.Save else True

    def populate(self, *_):
        selected = self.loaded
        self.list.blockSignals(True)
        self.list.clear()
        query = self.search.text().casefold()
        for snippet in self.store.data['snippets']:
            if query in '\n'.join((snippet['label'], snippet['shortcut'], snippet['text'])).casefold():
                item = QListWidgetItem(f"{snippet['label']}\n{snippet['shortcut']}")
                item.setData(Qt.ItemDataRole.UserRole, snippet['id'])
                self.list.addItem(item)
                if snippet['id'] == selected:
                    self.list.setCurrentItem(item)
        self.list.blockSignals(False)

    def select(self, current, previous):
        if current is None:
            return
        ident = current.data(Qt.ItemDataRole.UserRole)
        if ident == self.loaded:
            return
        if not self.confirm_changes():
            self.list.blockSignals(True)
            self.list.setCurrentItem(previous)
            self.list.blockSignals(False)
            return
        snippet = next((s for s in self.store.data['snippets'] if s['id'] == ident), None)
        if snippet:
            self.load_snippet(snippet)

    def load_snippet(self, snippet):
        self.loaded = snippet['id']
        self.original = snippet['label'], snippet['shortcut'], snippet['text']
        self.name.setText(self.original[0])
        self.shortcut.setText(self.original[1])
        self.text.setPlainText(self.original[2])
        self.delete_button.setEnabled(any(s['id'] == self.loaded for s in self.store.data['snippets']))
        self.update_hint()

    def new_snippet(self):
        if not self.confirm_changes():
            return
        self.load_snippet(dict(id=str(uuid.uuid4()), label='', shortcut='', text=''))
        self.list.blockSignals(True)
        self.list.clearSelection()
        self.list.blockSignals(False)
        self.tabs.setCurrentIndex(0)
        self.name.setFocus()

    def persist(self, candidate):
        try:
            self.store.save(candidate)
            self.engine.configure(self.store.data)
            self.clipboard_service.configure(self.store.data['settings'])
            self.refresh_status()
            return True
        except Exception as error:
            QMessageBox.warning(self, 'Could not save', str(error))
            return False

    def save_snippet(self):
        if self.loaded is None:
            return True
        name, shortcut, text = self.values()
        candidate = copy.deepcopy(self.store.data)
        snippet = dict(id=self.loaded, label=name, shortcut=shortcut, text=text)
        candidate['snippets'] = [snippet if s['id'] == self.loaded else s for s in candidate['snippets']]
        if not any(s['id'] == self.loaded for s in candidate['snippets']):
            candidate['snippets'].append(snippet)
        if not self.persist(candidate):
            return False
        saved = next(s for s in self.store.data['snippets'] if s['id'] == self.loaded)
        self.load_snippet(saved)
        self.populate()
        return True

    def delete_snippet(self):
        if QMessageBox.question(self, 'Delete snippet', 'Delete this saved snippet?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        candidate = copy.deepcopy(self.store.data)
        candidate['snippets'] = [s for s in candidate['snippets'] if s['id'] != self.loaded]
        if self.persist(candidate):
            self.original = self.values()
            self.loaded = None
            self.populate()
            if self.list.count():
                self.list.setCurrentRow(0)
            else:
                self.new_snippet()

    def load_settings(self):
        settings = self.store.data['settings']
        self.mode.setCurrentIndex(self.mode.findData(settings['trigger_mode']))
        self.keep_space.setChecked(settings['preserve_space'])
        self.titles.setPlainText('\n'.join(settings['excluded_titles']))
        self.processes.setPlainText('\n'.join(settings['excluded_processes']))
        self.clip_enabled.setChecked(settings['clipboard_enabled'])
        self.clip_strict.setChecked(settings['clipboard_strict'])
        self.clip_limit.setCurrentIndex(self.clip_limit.findData(settings['clipboard_limit']))
        self.clip_hotkey.setCurrentText(settings['clipboard_hotkey'])

    def save_clipboard_settings(self):
        candidate = copy.deepcopy(self.store.data)
        candidate['settings'].update(clipboard_enabled=self.clip_enabled.isChecked(),
            clipboard_strict=self.clip_strict.isChecked(), clipboard_limit=self.clip_limit.currentData(),
            clipboard_hotkey=self.clip_hotkey.currentText())
        if self.persist(candidate):
            self.load_settings()

    def save_settings(self):
        candidate = copy.deepcopy(self.store.data)
        settings = candidate['settings']
        settings['trigger_mode'] = self.mode.currentData()
        settings['preserve_space'] = self.keep_space.isChecked()
        settings['excluded_titles'] = [x.strip() for x in self.titles.toPlainText().splitlines() if x.strip()]
        settings['excluded_processes'] = [x.strip() for x in self.processes.toPlainText().splitlines() if x.strip()]
        if self.persist(candidate):
            self.load_settings()
            self.statusBar().showMessage('Expansion settings saved locally.', 5000)

    def change_startup(self, value):
        try:
            startup.set_enabled(value)
        except OSError as error:
            self.startup_check.setChecked(startup.enabled())
            QMessageBox.warning(self, 'Startup could not be changed', str(error))

    def reload(self):
        if not self.confirm_changes():
            return
        try:
            self.store.load()
            self.engine.configure(self.store.data)
            self.clipboard_service.configure(self.store.data['settings'])
            self.load_settings()
            self.loaded = None
            self.original = self.values()
            self.populate()
            if self.list.count():
                self.list.setCurrentRow(0)
            else:
                self.new_snippet()
        except Exception as error:
            QMessageBox.warning(self, 'Could not reload', f'{error}\nThe current library remains active.')

    def import_file(self):
        if not self.confirm_changes():
            return
        path, _ = QFileDialog.getOpenFileName(self, 'Import snippet library', '', 'YAML files (*.yaml *.yml)')
        if not path:
            return
        try:
            other = Store(Path(path))
            candidate = other.load()
            if QMessageBox.question(self, 'Replace library', f"Replace your library and expansion settings with {len(candidate['snippets'])} imported snippets? A backup is kept.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                if self.persist(candidate):
                    self.original = self.values()
                    self.reload()
        except Exception as error:
            QMessageBox.warning(self, 'Import failed', str(error))

    def export_file(self):
        if not self.confirm_changes():
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Export saved library', 'TwistType-backup.yaml', 'YAML files (*.yaml)')
        if path:
            try:
                Store(Path(path)).save(self.store.data)
            except Exception as error:
                QMessageBox.warning(self, 'Export failed', str(error))

    def toggle_pause(self):
        self.engine.pause(not self.engine.paused)
        self.refresh_status()

    def refresh_status(self):
        state = 'Paused' if self.engine.paused else ('Active' if self.engine.running else 'Engine stopped')
        action = 'Resume expansion' if self.engine.paused else 'Pause expansion'
        self.pause_button.setText(action)
        self.pause_action.setText(action)
        self.tray.setToolTip(f'TwistType • {state}')
        trigger = 'Space / Tab' if self.store.data['settings']['trigger_mode'] == 'delimiter' else 'Immediate'
        self.snippet_count.setText(str(len(self.store.data['snippets'])))
        self.trigger_summary.setText(trigger)
        self.clipboard_button.setText('Clipboard  ·  ' + self.store.data['settings']['clipboard_hotkey'])
        self.statusBar().showMessage(f"{state}   •   {len(self.store.data['snippets'])} snippets   •   {trigger}   •   {self.engine.count} expansions this session")

    def on_event(self, kind, payload):
        self.refresh_status()
        if kind == 'error':
            self.show_editor()
            QMessageBox.warning(self, 'TwistType needs attention', str(payload))

    def show_editor(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        if self.quitting:
            event.accept()
        elif self.tray.isVisible():
            if self.confirm_changes():
                # Discard means restore the saved version before hiding.
                if self.dirty():
                    saved = next((s for s in self.store.data['snippets'] if s['id'] == self.loaded), None)
                    if saved:
                        self.load_snippet(saved)
                    else:
                        self.original = self.values()
                self.hide()
                self.tray.showMessage('TwistType is running', 'Open the tray icon to edit, pause, or quit.', QSystemTrayIcon.MessageIcon.Information, 3000)
            event.ignore()
        elif self.confirm_changes():
            self.quit()
            event.accept()
        else:
            event.ignore()

    def quit(self):
        if not self.confirm_changes():
            return
        self.quitting = True
        self.clipboard_service.stop()
        self.picker.close()
        self.engine.stop()
        self.tray.hide()
        QApplication.quit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--background', action='store_true')
    parser.add_argument('--smoke-test', action='store_true', help='Render UI, write screenshot, exit without hooks or startup changes')
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName('TwistType')
    app.setOrganizationName('TwistType')
    apply_theme(app)
    app.setQuitOnLastWindowClosed(False)
    # Session-local singleton prevents double expansion from two running copies.
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.wintypes.BOOL, ctypes.wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = ctypes.wintypes.HANDLE
    mutex = None
    if not args.smoke_test:
        mutex = kernel.CreateMutexW(None, False, 'Local\\TwistType.Personal.v1')
        if not mutex:
            QMessageBox.critical(None, 'TwistType could not start', 'Could not create the single-instance lock.')
            return 1
        if ctypes.get_last_error() == 183:
            QMessageBox.information(None, 'TwistType is already running', 'Open TwistType from its system tray icon.')
            kernel.CloseHandle(mutex)
            return 0
    engine = None
    clipboard = None
    try:
        handler = RotatingFileHandler(data_dir() / 'twisttype.log', maxBytes=200_000, backupCount=1, encoding='utf-8')
        logging.basicConfig(handlers=[handler], level=logging.WARNING, format='%(asctime)s %(levelname)s %(message)s')
        store = Store()
        store.load()
        events = Events()
        engine = Engine(store.data, events.event.emit)
        history = HistoryStore(None if args.smoke_test else data_dir() / 'clipboard-history.dat',
                               store.data['settings']['clipboard_limit'], store.data['settings']['clipboard_strict'])
        history.load()
        clipboard = ClipboardService(history, store.data['settings'])
        window = Window(store, engine, events, clipboard)
        if args.smoke_test:
            window.show()
            def capture():
                window.grab().save(str(data_dir() / 'TwistType-preview.png'))
                window.tray.hide()
                app.quit()
            QTimer.singleShot(800, capture)
        else:
            engine.start()
            clipboard.start()
            if not args.background or not window.tray.isVisible():
                window.show()
        return app.exec()
    except Exception as error:
        logging.exception('Startup failed')
        QMessageBox.critical(None, 'TwistType could not start', f'{error}\n\nCheck %LOCALAPPDATA%\\TwistType. Existing files are never silently replaced with samples. Check snippets.yaml or restore snippets.yaml.bak.')
        return 1
    finally:
        if engine:
            engine.stop()
        if clipboard:
            clipboard.stop()
        if mutex:
            kernel.CloseHandle(mutex)


if __name__ == '__main__':
    raise SystemExit(main())
