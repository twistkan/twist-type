# TwistType verification — 2026-11-03

This is the first personal offline release. It was built locally on the user's Windows 10 PC (build 19045), using Python 3.14.8 x64, PySide6 Essentials 6.12.0, PyYAML 6.0.3, and PyInstaller 6.22.3.

## Checks passed

- 14 unit/editor tests: delimiter vs immediate matching; Space retention; Tab consumption; case; backspace; navigation/timeouts; whole-token matching; buffer length; reconfiguration; YAML roundtrip/backup; first-run seed; invalid/unsafe/oversize YAML; duplicates and immediate prefix collisions; required exclusions; UTF-16 surrogate pairs and native INPUT layout; editor create/save/search/settings/reload/delete/pause and invalid draft handling.
- 14 Windows integration checks using real installed low-level hooks and real SendInput against dedicated native Windows EDIT controls: Space with Greek/emoji; Tab without focus navigation; multiline; immediate; Shift/uppercase; title exclusion; exclusion buffer reset; classic password-field exclusion; process exclusion; pause; field focus change; corrected shortcut with Backspace; untrusted synthetic input; hooks remain installed after pause/exclusion. Six actual expansions completed with no engine error events.
- Original ICO generated at 16, 24, 32, 48, 64, 128, and 256 pixels; editor rendered and screenshot visually inspected.

The integration subclass admits only its unique test-tagged synthetic events into the production matching path by clearing their injected metadata. The normal app ignores synthetic input. The test uses no existing user documents, no registry changes, no clipboard changes, and cleans up its child window. Real human keyboard use across the user's everyday apps remains a separate practical check.

## Compatibility findings and limits

A Qt QPlainTextEdit test field reordered emoji within mixed text when the entire replacement was sent as one batch. Native Windows EDIT controls passed that same test. This limitation is disclosed in Help and README; emoji in Qt editors is not claimed supported. Windows elevation restrictions, app-specific Enter/Tab behavior, custom/browser password fields, games/remote sessions, IME composition, and other receiving-app differences remain limitations.

Windows startup command generation and UI are implemented, but actual sign-out/sign-in persistence has not been exercised; startup remains disabled. Windows 11 and a clean second PC have not been tested. Long-running background stability, code signing, and antivirus reputation are not established by these checks. The executable is unsigned.

## Packaged executable — 1.0.0 baseline

- PyInstaller single-file x64 executable: 47,800,913 bytes. PE subsystem 2 (Windows GUI), AMD64 machine type, icon resources present. No console subsystem.
- First-run test copied only the executable into a fresh folder and launched from a different working directory. Exit 0; it created valid `snippets.yaml`, an empty error log, and a rendered editor screenshot beside that executable. Embedded template and icon were present. No installed Python was used by the packaged app.
- Normal launch of the release EXE succeeded. Desktop accessibility inspection confirmed the actual window title, editor fields, sample library, and status: `Active / 2 snippets / Space / Tab / 0 expansions this session`. The app was left open for the user. Per-user startup registration was read as disabled.
- Build PATH is isolated to Python and Windows directories. This prevents an incompatible ICU/UCRT from an unrelated media-tool directory on the machine from being included. Final analysis contains no ICU/UCRT copies from those tools. The initial contaminated build was replaced and is not the delivered release.
- SHA256 (EXE): `49270E8F6871507B6B18CA2F145A355A9D2611F502453BB10F539EC743ACC761`.

## 1.0.1 popup visibility fix

Explicit light surfaces and dark text now cover QMenu/context menus, tray menus, and QComboBox item views, including selected and disabled rows. The Qt popup previously inherited a dark system background while the generic QWidget text rule supplied dark text.

The actual standard QLineEdit context menu, trigger-style dropdown, and tray-style menu were rendered using the production stylesheet with a deliberately dark Fusion application palette. All three screenshots in `qa/menu-contrast` were visually inspected and readable. Text contrast ratios are 15.60:1 for normal items, 6.23:1 for disabled items, and 7.27:1 for selected white text on teal. All 14 existing unit/editor checks passed during the rebuild. Keyboard expansion behavior is unchanged; the Windows insertion suite was not repeated for this styling change.

The update keeps the running session alive so drafts are not interrupted. Save drafts, quit via the tray, then reopen the updated executable to activate the theme. The existing snippet/settings YAML is preserved during packaging.

The 1.0.1 executable passed its isolated packaged smoke test (exit 0). The SHA256 of the saved snippet/settings YAML matched before and after installation. The old running executable was backed up under `release/previous`; the updated executable is installed at the usual `release/TwistType/TwistType.exe` path. SHA256 of the new EXE: `FF831E4B833DCC12C45B667912F570E06C43169F8645ADB4F2477408DBF3FF10`.

## 1.0.2 brighter popups

Context/tray menus and the dropdown use bright white text on navy with a vivid blue selected row. Disabled text is light blue-gray, and menu type is slightly larger/heavier. The combo now uses QStyledItemDelegate: Qt's default combo-menu delegate bypassed some item-view color settings. All three dark-palette renders were inspected again, including a highlighted text-menu command and both selected/unselected dropdown choices. Normal text contrast is 15.75:1 and selected text 4.83:1. The existing 14 unit/editor checks passed in the final rebuild.

Live app inspection found the original 1.0.0 process still running from the previously backed-up executable; the snippet editor showed Saved locally. The title bar now displays 1.0.2 to make a loaded update visible. Snippet/settings hashes are checked around installation; live restart and packaged launch results are recorded after packaging.

The rebuilt 1.0.2 EXE passed an isolated packaged smoke test (exit 0); saved library/settings SHA256 was unchanged. The old session exited during the build. The updated app was then launched, and live desktop inventory confirmed `TwistType 1.0.2 — Snippet Library` from the installed release path. EXE SHA256: `B82CAF2FB0349DAB75A9D849D09E730C3A83DF739C2F202C4BBB84841B5ED4BC`. Packaging now uses Python zipfile and the build-output EXE, avoiding PowerShell's exclusive lock on a running installed image.

## 1.1.0 clipboard history and theme

The UI now follows the supplied Theme.png reference's lavender sidebar, indigo navigation/actions, white editing panels, and pastel summary cards. No banking data, avatars, or reference artwork was copied. Existing bright popup styling remains in place. Library, clipboard, settings, help, and picker screens were rendered with synthetic clipboard entries and visually inspected. The actual encrypted user history is never used in screenshots or included in archives.

23 unit/editor checks passed: existing matching/storage/editor behavior plus history capacity/order/deduplication, secret filtering, source exclusion, DPAPI encryption roundtrip and encrypted disk persistence, corrupted history preservation/recovery, stricter-policy re-filtering, file/image limits, history search and previews, tray omission of protected content, configurable capacity/hotkey, pause/clear, and asynchronous busy-copy retries/cancellation.

13 live Windows clipboard checks passed in `tests/clipboard_integration.py`: latest 20 new copies, source identification, secret omission, both Windows sensitivity flags, PNG capture/replay, text replay without recapture, recording pause, file-path capture/replay, actual Ctrl+Alt+V WM_HOTKEY delivery, picker arrows/Escape, and pasting the chosen entry into the original native edit field in a dedicated child app. Test history is memory-only. The final passing run restored the clipboard formats present before it and flushed them through OLE. An earlier failing test could not restore the preceding clipboard and left synthetic test text there; no snippet data was changed.

Capture is deferred out of the QClipboard/OLE notification. Replay uses native owned HGLOBAL formats rather than delayed OLE rendering, retries a busy clipboard without blocking the UI, and invokes paste only after the requested content is present. Focus restoration checks the original process/window/child field and fails to manual Ctrl+V if it cannot restore them. Pending copy retries are invalidated on stop or a newer selection.

History is bounded to 10/20/50 distinct entries (20 default), 1 MB per item, 100 file paths, and 16 million image pixels. Persisted JSON is encrypted through user-scoped DPAPI in clipboard-history.dat; no plaintext history file or plaintext backup is created. The portable/source packagers omit history files. No account, network sync, or new third-party dependency was added.

Privacy is conservative, not perfect password recognition: single-token text is omitted by default along with known secret/token patterns, password-manager sources, sensitive source titles/identifiable classic password fields, and source-app privacy formats. Unmarked multiword passphrases and secrets within images can escape detection. Users can pause recording. Windows 11, every password manager, every browser password field, and arbitrary receiving apps have not been validated. Live password-manager contents were never inspected.

The final standalone 1.1.0 executable passed its isolated packaged smoke test (exit 0). The existing saved snippet/settings file's SHA256 matched before/after installation. Portable ZIP integrity passed, encrypted history was absent from the archive, and all three clipboard source modules were present in the source ZIP. EXE SHA256: `112E904946D645EA198D1B7AC7093983F2E1BA05FB4E099A2E5F513DA107E79C`. An older background session remained active; the user must quit it and reopen the updated executable to activate 1.1.0. We did not terminate that session or change Windows startup settings.

## 1.1.1 single-EXE / AppData storage

The default data path is now `%LOCALAPPDATA%\TwistType`; the EXE alone contains its runtime, icon, snippet template, notices, and license texts. First launch creates the folder and library. A clean `release/Single-EXE` delivery directory contains only TwistType.exe. Existing AppData wins over any executable-relative files. One-time migration copies the old snippets, backup, and encrypted history without changing their contents or removing the source files. Three explicit legacy locations relative to the EXE are checked; there is no broad drive scan. Invalid source YAML stops migration without creating a replacement library.

All 28 unit/editor checks passed, including 5 new storage cases: fresh automatic creation, byte-preserving migration and DPAPI history readability, retaining existing AppData after moving the EXE, migration from the adjacent old release folder, and preserving invalid legacy YAML without silently seeding samples. Packaged first-run/move checks follow the final build.

Four final packaged checks passed in `tests/check_single_exe.py`, using isolated LOCALAPPDATA directories: EXE-only first launch creates data/preview/logs and leaves the executable directory with exactly one file; a moved EXE reuses the unchanged AppData library; first upgrade copies exact legacy YAML/encrypted-history bytes while originals remain intact and the migrated history decrypts; template, icon, notices, and LGPL text are embedded in the archive. No real-user AppData migration was performed by the test; normal first launch from the supplied Single-EXE folder performs it after the old app has exited. SHA256: `3118E679CAD3C7A54C02DAF5ACB1D95D4DE41516AAC0AB7786E69520E6988886`.
