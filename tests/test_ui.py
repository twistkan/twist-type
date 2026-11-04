import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox
from core import Store
from twisttype import Events, Window
from theme import stylesheet
from test_core import data
from clipboard_core import HistoryStore
from clipboard_service import ClipboardBusy, ClipboardService
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt


class FakeEngine:
    running, paused, count = True, False, 0
    def configure(self, candidate):
        self.data = copy.deepcopy(candidate)
    def pause(self, value):
        self.paused = value
    def stop(self):
        pass


class EditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(stylesheet())

    def test_create_edit_search_settings_reload_and_pause(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'snippets.yaml')
            store.save(data())
            engine = FakeEngine()
            window = Window(store, engine, Events())
            try:
                window.new_snippet()
                window.name.setText('Client reply')
                window.shortcut.setText(';reply')
                window.text.setPlainText('Thank you, client!')
                self.assertTrue(window.dirty())
                self.assertTrue(window.save_snippet())
                self.assertFalse(window.dirty())
                self.assertEqual(len(Store(store.path).load()['snippets']), 2)
                window.search.setText('CLIENT')
                self.assertEqual(window.list.count(), 1)
                window.mode.setCurrentIndex(1)
                window.save_settings()
                self.assertEqual(store.data['settings']['trigger_mode'], 'immediate')
                window.toggle_pause()
                self.assertTrue(engine.paused)
                window.toggle_pause()
                self.assertFalse(engine.paused)
                window.reload()
                self.assertEqual(window.name.text(), 'Client reply')
                with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
                    window.delete_snippet()
                self.assertEqual(len(store.data['snippets']), 1)
                self.assertEqual(window.name.text(), '')
            finally:
                window.timer.stop()
                window.tray.hide()
                window.quitting = True
                window.close()

    def test_invalid_save_and_cancel_preserve_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'snippets.yaml')
            store.save(data())
            window = Window(store, FakeEngine(), Events())
            try:
                window.shortcut.setText('invalid')
                with patch.object(QMessageBox, 'warning'):
                    self.assertFalse(window.save_snippet())
                self.assertEqual(store.data['snippets'][0]['shortcut'], ';hi')
                with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Cancel):
                    window.new_snippet()
                self.assertEqual(window.shortcut.text(), 'invalid')
            finally:
                window.timer.stop()
                window.tray.hide()
                window.quitting = True
                window.close()

    def test_clipboard_panel_search_settings_and_tray_filtering(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'snippets.yaml')
            store.save(data())
            history = HistoryStore()
            history.add('text', 'A copied client reply', 'notepad.exe')
            history.add('text', 'Another copied paragraph', 'notepad.exe')
            self.assertFalse(history.add('text', 'password=do-not-display', 'test.exe'))
            service = ClipboardService(history, store.data['settings'])
            window = Window(store, FakeEngine(), Events(), service)
            try:
                window.tabs.setCurrentIndex(3)
                self.assertEqual(window.navigation.currentRow(), 1)
                self.assertEqual(window.clipboard_panel.list.count(), 2)
                window.clipboard_panel.search.setText('client')
                self.assertEqual(window.clipboard_panel.list.count(), 1)
                self.assertEqual(window.clipboard_panel.preview.toPlainText(), 'A copied client reply')
                window.populate_recent_menu()
                text = '\n'.join(a.text() for a in window.recent_menu.actions())
                self.assertNotIn('do-not-display', text)
                self.assertIn('client reply', text)
                window.clip_limit.setCurrentIndex(window.clip_limit.findData(10))
                window.clip_hotkey.setCurrentText('Ctrl+Alt+Shift+V')
                window.save_clipboard_settings()
                self.assertEqual(history.limit, 10)
                self.assertEqual(store.data['settings']['clipboard_hotkey'], 'Ctrl+Alt+Shift+V')
                window.picker.refresh()
                window.picker.search.setText('paragraph')
                self.assertEqual(window.picker.list.count(), 1)
                window.clipboard_panel.toggle_pause()
                self.assertTrue(service.suspended)
                with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
                    window.clipboard_panel.clear()
                self.assertEqual(history.items, [])
                self.assertEqual(window.clipboard_panel.list.count(), 0)
            finally:
                window.timer.stop()
                window.tray.hide()
                window.picker.close()
                window.quitting = True
                window.close()

    def test_busy_replay_retries_and_stop_cancels_pending_copy(self):
        history = HistoryStore()
        history.add('text', 'A safe copied sample', 'notepad.exe')
        service = ClipboardService(history, data()['settings'])
        ready = []
        with patch('clipboard_service.write_clipboard', side_effect=[ClipboardBusy(), None]) as writer:
            service.copy_item(history.items[0], on_ready=lambda: ready.append(True))
            self.assertFalse(ready)
            QTest.qWait(90)
            self.assertEqual(writer.call_count, 2)
            self.assertEqual(ready, [True])
        ready.clear()
        with patch('clipboard_service.write_clipboard', side_effect=ClipboardBusy()) as writer:
            service.copy_item(history.items[0], on_ready=lambda: ready.append(True))
            service.stop()
            QTest.qWait(90)
            self.assertEqual(writer.call_count, 1)
            self.assertFalse(ready)
