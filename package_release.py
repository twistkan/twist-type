"""Package the verified build without exclusively locking the running app image."""
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent
RELEASE = ROOT / 'release' / 'TwistType'
VERSION = '1.1.1'


def main():
    single = ROOT / 'release' / 'Single-EXE'
    single.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / 'dist' / 'TwistType.exe', single / 'TwistType.exe')
    portable = ROOT / 'release' / f'TwistType-{VERSION}-portable.zip'
    with zipfile.ZipFile(portable, 'w', zipfile.ZIP_DEFLATED) as archive:
        # Use the build output; PowerShell's ZIP helper requests exclusive access
        # to the installed image, which fails while TwistType is running.
        archive.write(ROOT / 'dist' / 'TwistType.exe', 'TwistType.exe')
        for name in ('README.md', 'THIRD-PARTY.md', 'VALIDATION.md', 'licenses'):
            path = RELEASE / name
            for file in ([path] if path.is_file() else path.rglob('*')):
                if file.is_file():
                    archive.write(file, file.relative_to(RELEASE).as_posix())
    roots = ['core.py', 'win_engine.py', 'twisttype.py', 'theme.py', 'startup.py', 'requirements.txt',
             'clipboard_core.py', 'clipboard_service.py', 'clipboard_ui.py',
             'build.ps1', 'package_release.py', 'snippets.yaml', 'README.md', 'THIRD-PARTY.md',
             'VALIDATION.md', 'assets', 'tests', 'replica', 'qa/verify_menu_contrast.py', 'qa/menu-contrast']
    with zipfile.ZipFile(ROOT / 'release' / f'TwistType-{VERSION}-source.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in roots:
            path = ROOT / name
            for file in ([path] if path.is_file() else path.rglob('*')):
                if file.is_file() and '__pycache__' not in file.parts and file.suffix != '.pyc':
                    archive.write(file, file.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(portable) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Portable ZIP integrity check failed.')
    print(f'Packaged TwistType {VERSION}; ZIP integrity passed.')


if __name__ == '__main__':
    main()
