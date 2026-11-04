"""Validate the packaged EXE alone with isolated LOCALAPPDATA directories."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core import Store, DEFAULT_SETTINGS
from clipboard_core import HistoryStore


def main():
    work = ROOT / 'qa' / 'single-exe-1.1.1'
    work.mkdir(parents=True, exist_ok=True)
    checks = []
    built = ROOT / 'release' / 'Single-EXE' / 'TwistType.exe'

    def install(folder):
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(built, folder / 'TwistType.exe')
        return folder / 'TwistType.exe'

    def run(executable, local):
        env = dict(os.environ, LOCALAPPDATA=str(local))
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        info.wShowWindow = 0
        result = subprocess.run([str(executable), '--smoke-test'], env=env, cwd=ROOT,
                                startupinfo=info, timeout=40)
        assert result.returncode == 0, result.returncode
        assert sorted(p.name for p in executable.parent.iterdir()) == ['TwistType.exe']
        return local / 'TwistType'

    first = install(work / 'fresh')
    local = work / 'fresh-local'
    data = run(first, local)
    assert (data / 'snippets.yaml').is_file()
    assert (data / 'TwistType-preview.png').is_file()
    checks.append('EXE alone creates AppData library/log/preview without loose companion assets')
    store = Store(data / 'snippets.yaml')
    store.load()
    store.data['snippets'][0]['label'] = 'Kept after moving the EXE'
    store.save(store.data)
    before = (data / 'snippets.yaml').read_bytes()
    moved = install(work / 'moved')
    run(moved, local)
    assert (data / 'snippets.yaml').read_bytes() == before
    checks.append('Moving EXE preserves the same AppData library without overwriting it')

    legacy = work / 'upgrade' / 'TwistType'
    legacy.mkdir(parents=True, exist_ok=True)
    sample = {'version': 1, 'settings': dict(DEFAULT_SETTINGS), 'snippets': [
        {'id': 'legacy', 'label': 'Legacy test entry', 'shortcut': ';legacy', 'text': 'Existing test words'}]}
    Store(legacy / 'snippets.yaml').save(sample)
    history = HistoryStore(legacy / 'clipboard-history.dat')
    history.add('text', 'Existing test clipboard entry', 'notepad.exe')
    history.save()
    old = {name: (legacy / name).read_bytes() for name in ('snippets.yaml', 'clipboard-history.dat')}
    upgrade = install(work / 'upgrade' / 'Single-EXE')
    upgraded = run(upgrade, work / 'upgrade-local')
    for name, raw in old.items():
        assert (legacy / name).read_bytes() == raw
        assert (upgraded / name).read_bytes() == raw
    loaded = HistoryStore(upgraded / 'clipboard-history.dat')
    loaded.load()
    assert loaded.items == history.items
    checks.append('First launch migrates exact legacy snippet/history bytes; sources remain intact and history decrypts')

    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(str(built))
    for name in ('snippets.yaml', 'assets/twisttype.ico', 'THIRD-PARTY.md', 'licenses/LGPL-3.0.txt'):
        assert name in {n.replace('\\', '/') for n in archive.toc}, name
    checks.append('Template, icon, notices, and LGPL text are embedded')
    output = {'passed': len(checks), 'checks': checks,
              'exe_sha256': hashlib.sha256(built.read_bytes()).hexdigest()}
    (work / 'results.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
