"""Inspect the built APK; does not install, grant permissions, or read a phone."""
import hashlib
import json
import re
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT.parent / 'MobileTrans App' / 'tools'
JAVA = next((TOOLS / 'java').glob('jdk-*/bin/java.exe'))
BUILD = TOOLS / 'sdk' / 'build-tools' / 'android-15'
APK = ROOT / 'release' / 'Android' / 'TwistType-Android-1.0.2.apk'


def run(*args):
    result = subprocess.run([str(a) for a in args], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def main():
    checks = []
    with zipfile.ZipFile(APK) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert 'classes.dex' in names and 'resources.arsc' in names and 'AndroidManifest.xml' in names
        assert not any(n.endswith(('.jks', '.keystore')) or 'password.txt' in n for n in names)
        dex = archive.read('classes.dex')
        for name in ('MainActivity', 'TestActivity', 'ExpandService', 'ClipboardService', 'Logic', 'Data', 'ClipboardTileService', 'ClipboardEntryActivity'):
            assert ('Lcom/twisttype/android/' + name + ';').encode() in dex, name
        assert b'AndroidKeyStore' in dex and b'AES/GCM/NoPadding' in dex
        checks += ['APK ZIP integrity and required code/resources', 'No private signing files in APK',
                   'All application components present in DEX', 'Keystore/AES-GCM implementation included']
        assert not any(n.startswith('lib/') for n in names)
        checks.append('Universal DEX package without CPU-specific native libraries')
    badging = run(BUILD / 'aapt.exe', 'dump', 'badging', APK)
    assert "name='com.twisttype.android'" in badging and "versionName='1.0.2'" in badging and "versionCode='3'" in badging
    assert "sdkVersion:'26'" in badging and "targetSdkVersion:'28'" in badging
    assert "launchable-activity: name='com.twisttype.android.MainActivity'" in badging
    permissions = [line for line in badging.splitlines() if line.startswith('uses-permission:')]
    assert permissions == ["uses-permission: name='android.permission.FOREGROUND_SERVICE'"]
    checks += ['Package ID/version and launcher verified', 'Minimum API26 / Android9 target API28',
               'Only normal foreground-service permission requested; no INTERNET/storage/contacts permission']
    manifest = run(BUILD / 'aapt.exe', 'dump', 'xmltree', APK, 'AndroidManifest.xml')
    assert 'android.permission.BIND_ACCESSIBILITY_SERVICE' in manifest
    assert 'android:allowBackup' in manifest and 'android:allowBackup(0x01010280)=(type 0x12)0x0' in manifest
    checks.append('Accessibility binding is protected and backup is disabled')
    nodes = re.split(r'(?m)^\s+E: ', manifest)
    tile = next(n for n in nodes if n.startswith('service ') and '.ClipboardTileService' in n)
    assert 'android.permission.BIND_QUICK_SETTINGS_TILE' in tile
    assert 'android:exported(0x01010010)=(type 0x12)0xffffffff' in tile
    assert 'android.service.quicksettings.action.QS_TILE' in manifest
    checks.append('Discoverable Quick Settings service is protected by the system tile binding permission')
    entry = next(n for n in nodes if n.startswith('activity ') and '.ClipboardEntryActivity' in n)
    assert 'TT Clipboard' in entry and 'android:theme' in entry and 'android:icon' in entry
    assert 'android:exported(0x01010010)=(type 0x12)0xffffffff' in entry
    assert 'android:excludeFromRecents(0x01010017)=(type 0x12)0xffffffff' in entry
    # Two launcher filters: original TwistType and the dedicated Apps Edge entry.
    assert sum('android.intent.category.LAUNCHER' in line for line in manifest.splitlines()) == 2
    checks.append('Dedicated clipboard launcher with icon/theme is exported and excluded from Recents')
    with zipfile.ZipFile(APK) as archive:
        assert 'res/drawable/ic_clipboard_tile.xml' in archive.namelist()
        assert 'res/drawable/ic_clipboard_launcher.xml' in archive.namelist()
    checks.append('Monochrome tile and colored clipboard launcher icons are packaged')
    signature = run(JAVA, '-jar', BUILD / 'lib' / 'apksigner.jar', 'verify', '--verbose',
                    '--min-sdk-version', '28', '--max-sdk-version', '28', APK)
    assert 'Verifies' in signature and 'Number of signers: 1' in signature
    checks.append('Signature verifies for actual Android9/API28 verifier settings')
    previous = APK.with_name('TwistType-Android-1.0.0.apk')
    if previous.exists():
        def cert(apk):
            details = run(JAVA, '-jar', BUILD / 'lib' / 'apksigner.jar', 'verify', '--print-certs', apk)
            return next(line for line in details.splitlines() if 'certificate SHA-256 digest:' in line)
        assert cert(APK) == cert(previous), 'Update signing certificate changed'
        checks.append('Signing certificate matches 1.0.0 for in-place updates')
    run(BUILD / 'zipalign.exe', '-c', '4', APK)
    checks.append('APK alignment verified')
    output = {'checks_passed': len(checks), 'checks': checks, 'apk_bytes': APK.stat().st_size,
              'sha256': hashlib.sha256(APK.read_bytes()).hexdigest(), 'real_phone_tested': False}
    (ROOT / 'android' / 'apk-check-results.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
