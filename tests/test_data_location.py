import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml
from core import DEFAULT_SETTINGS, Store, data_dir, migrate_legacy
from clipboard_core import HistoryStore


def sample(text='My existing words'):
    return {'version': 1, 'settings': copy.deepcopy(DEFAULT_SETTINGS), 'snippets': [
        {'id': 'kept', 'label': 'My snippet', 'shortcut': ';mine', 'text': text}]}


class DataLocationTests(unittest.TestCase):
    def test_first_launch_creates_appdata_from_embedded_template(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            empty_executable = root / 'app'
            empty_executable.mkdir()
            with patch.dict(os.environ, {'LOCALAPPDATA': str(root / 'local')}), patch('core.app_dir', return_value=empty_executable):
                store = Store()
                self.assertEqual(store.path, root / 'local' / 'TwistType' / 'snippets.yaml')
                store.load()
                self.assertTrue(store.path.is_file())
                self.assertGreater(len(store.data['snippets']), 0)
                self.assertFalse((empty_executable / 'snippets.yaml').exists())

    def test_migrates_snippets_backup_and_encrypted_history_without_touching_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            legacy, destination = root / 'old', root / 'new'
            legacy.mkdir()
            Store(legacy / 'snippets.yaml').save(sample())
            (legacy / 'snippets.yaml.bak').write_text('previous backup', encoding='utf-8')
            history = HistoryStore(legacy / 'clipboard-history.dat')
            history.add('text', 'An existing clipboard entry', 'notepad.exe')
            history.save()
            before = {p.name: p.read_bytes() for p in legacy.iterdir()}
            self.assertTrue(migrate_legacy(destination, [legacy]))
            for name, raw in before.items():
                self.assertEqual((legacy / name).read_bytes(), raw)
                self.assertEqual((destination / name).read_bytes(), raw)
            loaded = HistoryStore(destination / 'clipboard-history.dat')
            loaded.load()
            self.assertEqual(loaded.items, history.items)

    def test_existing_appdata_wins_and_survives_executable_move(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            first, second, destination = root / 'first', root / 'second', root / 'local' / 'TwistType'
            first.mkdir()
            second.mkdir()
            destination.mkdir(parents=True)
            Store(first / 'snippets.yaml').save(sample('Old install'))
            Store(destination / 'snippets.yaml').save(sample('Current AppData'))
            self.assertFalse(migrate_legacy(destination, [first]))
            with patch.dict(os.environ, {'LOCALAPPDATA': str(root / 'local')}), patch('core.app_dir', return_value=second):
                loaded = Store()
                loaded.load()
                self.assertEqual(loaded.data['snippets'][0]['text'], 'Current AppData')

    def test_single_exe_release_finds_adjacent_legacy_install(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            single, legacy = root / 'release' / 'Single-EXE', root / 'release' / 'TwistType'
            single.mkdir(parents=True)
            legacy.mkdir()
            Store(legacy / 'snippets.yaml').save(sample())
            with patch.dict(os.environ, {'LOCALAPPDATA': str(root / 'local')}), patch('core.app_dir', return_value=single):
                store = Store()
                store.load()
                self.assertEqual(store.data['snippets'][0]['text'], 'My existing words')

    def test_bad_legacy_yaml_does_not_seed_or_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            legacy = root / 'old'
            legacy.mkdir()
            (legacy / 'snippets.yaml').write_text('snippets: [invalid', encoding='utf-8')
            with self.assertRaises(yaml.YAMLError):
                migrate_legacy(root / 'new', [legacy])
            self.assertFalse((root / 'new' / 'snippets.yaml').exists())
