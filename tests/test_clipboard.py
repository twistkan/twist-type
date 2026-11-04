import base64
from pathlib import Path
import tempfile
import unittest

from clipboard_core import HistoryStore, crypt, likely_secret, preview, valid_item


class ClipboardCoreTests(unittest.TestCase):
    def test_capacity_duplicates_and_order(self):
        history = HistoryStore()
        for i in range(27):
            self.assertTrue(history.add('text', f'Copied note number {i}', 'notepad.exe'))
        self.assertEqual(len(history.items), 20)
        self.assertEqual(history.items[0]['value'], 'Copied note number 26')
        history.add('text', 'Copied note number 12', 'notepad.exe')
        self.assertEqual(len(history.items), 20)
        self.assertEqual(history.items[0]['value'], 'Copied note number 12')
        history.configure(10, True)
        self.assertEqual(len(history.items), 10)

    def test_sensitive_text_and_sources_never_enter_history(self):
        history = HistoryStore()
        for text in ('hunter2', 'P@ssword123', '123456', 'password: a long secret',
                     'api_key=abc123', 'https://example.com/?token=abc',
                     'https://user:secret@example.com', '-----BEGIN PRIVATE KEY-----'):
            self.assertFalse(history.add('text', text, 'notepad.exe'))
        self.assertFalse(history.add('text', 'ordinary note copied', 'KeePassXC.EXE'))
        self.assertEqual(history.items, [])
        self.assertTrue(history.add('text', 'ordinary note copied', 'notepad.exe'))
        self.assertTrue(history.add('text', 'https://example.com/docs', 'msedge.exe'))

    def test_relaxed_mode_and_stricter_policy_reapply(self):
        history = HistoryStore(strict=False)
        self.assertTrue(history.add('text', 'hello', 'notepad.exe'))
        self.assertFalse(history.add('text', 'Ab3$randomsecret', 'notepad.exe'))
        history.configure(20, True)
        self.assertEqual(history.items, [])
        self.assertFalse(likely_secret('A normal phrase can include punctuation.'))

    def test_dpapi_roundtrip_and_encrypted_persistence(self):
        text = 'Test note that must not be plaintext on disk.'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'clipboard-history.dat'
            history = HistoryStore(path)
            history.add('text', text, 'notepad.exe')
            history.save()
            self.assertNotIn(text.encode(), path.read_bytes())
            other = HistoryStore(path)
            other.load()
            self.assertEqual(other.items, history.items)
            self.assertEqual(crypt(crypt(b'local private data'), decrypt=True), b'local private data')
            other.remove(other.items[0]['id'])
            again = HistoryStore(path)
            again.load()
            self.assertEqual(again.items, [])

    def test_unreadable_file_preserved_until_explicit_clear(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'clipboard-history.dat'
            path.write_bytes(b'not a valid DPAPI payload')
            history = HistoryStore(path)
            history.load()
            self.assertTrue(history.error)
            with self.assertRaises(OSError):
                history.save()
            self.assertEqual(path.read_bytes(), b'not a valid DPAPI payload')
            history.clear()
            self.assertFalse(history.error)
            reloaded = HistoryStore(path)
            reloaded.load()
            self.assertFalse(reloaded.error)
            self.assertEqual(reloaded.items, [])

    def test_images_files_and_size_limits(self):
        history = HistoryStore()
        self.assertTrue(history.add('files', ['C:/Notes/note.txt'], 'explorer.exe'))
        self.assertEqual(preview(history.items[0]), 'note.txt')
        self.assertTrue(history.add('image', base64.b64encode(b'\x89PNG\r\n\x1a\n').decode(), 'test.exe'))
        self.assertEqual(preview(history.items[0]), 'Image copied to clipboard')
        with self.assertRaises(ValueError):
            history.add('text', 'a ' * 600_000, 'test.exe')
        with self.assertRaises(ValueError):
            history.add('image', 'not base64', 'test.exe')

    def test_load_filters_current_secret_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'clipboard-history.dat'
            history = HistoryStore(path, strict=False)
            history.add('text', 'hello', 'notepad.exe')
            history.add('text', 'a safe phrase', 'notepad.exe')
            history.save()
            other = HistoryStore(path, strict=True)
            other.load()
            self.assertEqual([i['value'] for i in other.items], ['a safe phrase'])
