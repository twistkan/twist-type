import copy
from pathlib import Path
import tempfile
import unittest

import yaml

from core import DEFAULT_SETTINGS, Matcher, Store, excluded, validate


def data(mode='delimiter'):
    return dict(version=1, settings=dict(copy.deepcopy(DEFAULT_SETTINGS), trigger_mode=mode),
                snippets=[dict(id='1', label='Hello', shortcut=';hi', text='Hello 👋\nWorld')])


class MatchingTests(unittest.TestCase):
    def type(self, matcher, text):
        result = None
        for char in text:
            result = matcher.feed(char)
        return result

    def test_delimiters_and_preserved_space(self):
        m = Matcher(data())
        self.assertIsNone(self.type(m, ';hi'))
        self.assertEqual(m.feed('SPACE'), (3, 'Hello 👋\nWorld '))
        self.type(m, ';hi')
        self.assertEqual(m.feed('TAB'), (3, 'Hello 👋\nWorld'))
        self.assertIsNone(m.feed('TAB'))

    def test_immediate_consumes_final_character(self):
        m = Matcher(data('immediate'))
        self.assertEqual(self.type(m, ';hi'), (2, 'Hello 👋\nWorld'))
        self.assertIsNone(m.feed('SPACE'))

    def test_backspace_navigation_timeout_and_case(self):
        m = Matcher(data())
        self.type(m, ';hx')
        m.feed('BACKSPACE')
        m.feed('i')
        self.assertIsNotNone(m.feed('TAB'))
        self.type(m, ';hi')
        m.feed('LEFT')
        self.assertIsNone(m.feed('TAB'))
        self.type(m, ';HI')
        self.assertIsNone(m.feed('SPACE'))
        m.feed(';', now=100)
        m.feed('h', now=101)
        m.feed('i', now=120)
        self.assertIsNone(m.feed('TAB', now=121))

    def test_whole_token_and_overflow(self):
        m = Matcher(data())
        self.type(m, 'hello;hi')
        self.assertIsNone(m.feed('SPACE'))
        d = data()
        d['snippets'][0]['shortcut'] = ';' + 'x' * 39
        m = Matcher(d)
        self.type(m, 'a' * 40 + ';' + 'x' * 39)
        self.assertIsNone(m.feed('SPACE'))
        self.type(m, ';' + 'x' * 39)
        self.assertIsNotNone(m.feed('SPACE'))

    def test_settings_reconfigure_resets_partial_token(self):
        m = Matcher(data())
        self.type(m, ';h')
        m.configure(data('immediate'))
        self.assertIsNone(m.feed('i'))


class StorageTests(unittest.TestCase):
    def test_atomic_roundtrip_backup_and_reject_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'snippets.yaml'
            store = Store(path)
            store.save(data())
            first = path.read_bytes()
            d = data('immediate')
            store.save(d)
            self.assertEqual(path.with_suffix('.yaml.bak').read_bytes(), first)
            self.assertEqual(Store(path).load(), validate(d))
            broken = copy.deepcopy(d)
            broken['snippets'].append(broken['snippets'][0])
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                store.save(broken)
            self.assertEqual(path.read_bytes(), before)
            path.write_text('snippets: [broken', encoding='utf-8')
            with self.assertRaises(yaml.YAMLError):
                store.load()
            self.assertEqual(store.data, validate(d))

    def test_missing_file_seeds_template(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'snippets.yaml'
            self.assertGreater(len(Store(path).load()['snippets']), 0)
            self.assertTrue(path.exists())

    def test_safe_yaml_and_size_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'snippets.yaml'
            path.write_text('!!python/object/apply:os.system ["invalid"]', encoding='utf-8')
            with self.assertRaises(yaml.YAMLError):
                Store(path).load()
            path.write_bytes(b' ' * 2_000_001)
            with self.assertRaises(ValueError):
                Store(path).load()

    def test_duplicate_and_prefix_collisions(self):
        d = data('immediate')
        d['snippets'].append(dict(id='2', label='Second', shortcut=';higher', text='x'))
        with self.assertRaises(ValueError):
            validate(d)
        d['settings']['trigger_mode'] = 'delimiter'
        validate(d)
        d['snippets'][1]['shortcut'] = ';hi'
        with self.assertRaises(ValueError):
            validate(d)

    def test_invalid_text_and_shortcuts(self):
        for text in ('', 'x\0', 'x' * 8193):
            d = data()
            d['snippets'][0]['text'] = text
            with self.assertRaises(ValueError):
                validate(d)
        for shortcut in ('word', ';x x', ';é', ';' + 'x' * 40):
            d = data()
            d['snippets'][0]['shortcut'] = shortcut
            with self.assertRaises(ValueError):
                validate(d)

    def test_default_exclusions_always_merged(self):
        d = data()
        d['settings']['excluded_titles'] = []
        d['settings']['excluded_processes'] = []
        s = validate(d)['settings']
        self.assertTrue(excluded('Windows POWERSHELL', 'other.exe', s))
        self.assertTrue(excluded('private database', 'KEEPASSXC.EXE', s))
        self.assertFalse(excluded('Notes', 'notepad.exe', s))
        s['excluded_titles'].append('Private client')
        self.assertTrue(excluded('Notes - PRIVATE CLIENT', 'notepad.exe', s))


class WindowsStructureTests(unittest.TestCase):
    def test_input_abi_and_surrogate_pairs(self):
        import ctypes
        from win_engine import INPUT, replacement_inputs
        self.assertEqual(ctypes.sizeof(INPUT), 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
        events = replacement_inputs(3, 'A😀\n\t')
        self.assertEqual(len(events), 16)
        self.assertEqual(events[0].ki.wVk, 8)
        self.assertEqual(events[6].ki.wScan, ord('A'))
        self.assertEqual(events[8].ki.wScan, 0xD83D)
        self.assertEqual(events[10].ki.wScan, 0xDE00)
        self.assertEqual(events[12].ki.wVk, 13)
        self.assertEqual(events[14].ki.wVk, 9)


if __name__ == '__main__':
    unittest.main()
