# TwistType 1.1.1

**Windows download:** [Latest release](https://github.com/twistkan/twist-type/releases/latest). This repository contains source code; packaged executables are in Releases.


Personal, offline text expansion and clipboard history for Windows 10/11, x64. No Python installation is needed to run the packaged EXE.

## Run

1. Use **`release\Single-EXE\TwistType.exe`**. It is the only file needed to run the app. You can keep it in Documents, on the Desktop, or another permanent location. The ZIP is an optional package with documentation.
2. Double-click `TwistType.exe`. No installer, Python installation, console, or administrator access is needed. It automatically creates `%LOCALAPPDATA%\TwistType` for your data. The initial launch of a one-file app takes longer while Qt is unpacked.
3. Select **Simple sign-off**, replace the placeholder name, and click **Save snippet**. Or create your own shortcut, such as `;address`.
4. Open Notepad and type `;sig`, then Space or Tab. Space is retained by default. Tab expands and is consumed, so focus stays in the field. Toggle immediate expansion in **Settings** if preferred.
5. Closing the editor keeps the app in the system tray (possibly under the Windows hidden-icons arrow). Double-click the tray icon to reopen it; right-click to pause, reload, or quit.
6. Press **Ctrl+Alt+V** anywhere to open clipboard history. Search or use Up/Down, then Enter to choose and paste. Esc closes the picker. The sidebar opens a full preview screen; the tray shows the last 10 saved entries for copying.

Startup is off by default. Enable **Start TwistType when I sign in to Windows** to register the current app location in `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, value `TwistType`. Uncheck it before moving or removing the app. After moving it, re-enable startup from the new location. Startup uses `--background` to open only the tray icon. No machine-wide registry changes are made.

To remove TwistType, disable startup, quit from the tray, and remove its EXE. Saved data stays in `%LOCALAPPDATA%\TwistType` until you remove that folder yourself. Keep an exported library if needed.

## Snippets and behavior

- Snippets, settings, exclusions, backups, logs, and encrypted history live in **`%LOCALAPPDATA%\TwistType`**, separately from the EXE and PyInstaller's temporary extraction folder. `snippets.yaml` is created automatically from the embedded template on a fresh installation. Moving or replacing the EXE retains the same data.
- On the first upgrade from an older folder-based version, quit the old app and launch the new EXE from its supplied `release\Single-EXE` location once. If AppData has no library yet, TwistType copies the existing `snippets.yaml`, backup, and encrypted history from the older adjacent `release\TwistType` folder (or from beside the EXE). Old files remain untouched. Existing AppData always wins. Invalid old YAML stops migration with an error rather than silently replacing it with examples. After that first launch, the EXE can be moved freely; refresh the Startup checkbox if its path changes.
- Saves use a temporary file and atomic replacement, keeping one previous version in `snippets.yaml.bak`. Back up/export important snippets separately. Import replaces both the library and expansion settings after confirmation. It does not change Windows startup.
- YAML edited externally takes effect using **Reload snippets from disk**. Invalid YAML is rejected; it is never silently overwritten. A startup error can be fixed by restoring the `.bak` file after quitting.
- Shortcuts are case-sensitive ASCII, 2–40 characters, start with `; : / ! . ,`, and contain no whitespace. Use a distinct prefix and an entire typed token: `hello;sig` does not expand. Typing non-ASCII characters, navigating, clicking, switching fields/windows, or waiting 15 seconds clears the match buffer. Backspace updates it. Paste and synthetic input do not trigger expansion.
- Immediate mode rejects overlapping shortcuts (`;sig` and `;signature`) because the shorter one would fire first.
- Plain text supports Unicode and line breaks, up to 8192 UTF-16 units per snippet. Newlines are inserted as Enter and embedded tabs as Tab: in forms and chat apps those keys can navigate or submit, so use single-line snippets there. Formatting, images, scripts, fill-in dialogs, sync, and cloud accounts are outside this first version.
- Known compatibility limit: a Qt `QPlainTextEdit` test field reordered mixed text containing an emoji during a batched insertion. Native Windows EDIT controls passed the same Unicode/emoji test. Avoid emoji in snippets targeting Qt editors until that path has been improved; ordinary application compatibility still needs checking in the apps you use.
- Snippet expansion uses Windows `SendInput` without replacing the clipboard. The separate clipboard-history feature watches new copies and replaces the current clipboard only when you choose a history entry. No typed-content log, cloud requests, or analytics are implemented. Error logs rotate locally (`twisttype.log`, maximum two 200 KB files). Snippets and backups are ordinary unencrypted local files; avoid storing secrets.
- Command Prompt, PowerShell, Windows Terminal, KeePass, KeePassXC, 1Password, and Bitwarden are excluded by title/process as configured. Required default rules are always merged back in. Add extra app names or title phrases in Settings. Exclusions are case-insensitive; process names are exact; title phrases are substring matches. Windows with an inaccessible process are skipped. The TwistType editor is excluded too.
- Classic Windows password edit fields are skipped where identifiable. Browser/custom password fields cannot be detected reliably: exclude sensitive apps or pause from the tray. Global hooks remain installed while paused/excluded; matching buffers are cleared and ordinary typing passes through.
- Run at normal user permissions. Windows can block insertion into elevated apps; TwistType pauses if insertion fails. Some games, remote sessions, custom editors, and IME/dead-key composition may behave differently; test the apps you use. Shift/Caps Lock work for ordinary Latin shortcuts; Ctrl/Alt/Win combinations reset the buffer. The app never requests elevation.
- Launching a second copy shows a message instead of installing duplicate hooks. Windows may require **More info → Run anyway** for this unsigned, locally built executable; this release has no code-signing certificate.

## Clipboard history and privacy

- **Ctrl+Alt+V** opens a searchable picker across ordinary desktop apps. Up/Down selects; Enter restores the item and pastes into the original field after verifying its window/process. Esc dismisses it. If Windows cannot restore the field or blocks input into an elevated app, the item remains copied for manual Ctrl+V. Settings offers **Ctrl+Alt+Shift+V** if the default shortcut is already in use.
- The latest **20 distinct items** are retained by default; choose 10, 20, or 50 in Settings. Text, images encoded as PNG, and copied local file paths are supported. Each item is bounded to 1 MB; images are also limited to 16 million pixels and file lists to 100 paths. Large/unsupported clipboard formats are skipped. File contents are not copied into TwistType's storage. Rich-text formatting is not retained.
- History begins with **new copies after launch**; the pre-existing clipboard is not imported. Updates are event-driven. Snippet expansion and clipboard recording have separate pause controls. Disabling recording retains existing entries; **Clear clipboard history** removes them. Clicking a history item replaces the current system clipboard; normal capture leaves it alone.
- Entries and their source/timestamps are saved in `%LOCALAPPDATA%\TwistType\clipboard-history.dat`, encrypted with Windows DPAPI for the current Windows account. They survive restarts and EXE moves on this PC/account. History is omitted from portable/source ZIPs, snippet imports/exports, backups, logs, and telemetry. The app has no cloud sync. DPAPI does not protect against other software running as your logged-in account.
- Protected entries are **omitted entirely**, including their previews. The app honors Windows `ExcludeClipboardContentFromMonitorProcessing` and `CanIncludeInClipboardHistory=0`, password-manager hints, known password-manager processes, identifiable classic password fields, and sensitive window titles. Unknown/inaccessible sources are skipped.
- Text filtering rejects password/secret/API-key assignments, common token/private-key patterns, likely OTPs, URL credentials and sensitive URL parameters. **Hide single-word copies** is on by default; it omits single-token text such as words and passwords while allowing ordinary web links and phrases. Turning it off still retains the other secret filters. This intentionally favors privacy over retaining every ordinary word.
- **No automatic filter can identify every password in unmarked ordinary text or images.** Multiword passphrases can resemble normal sentences. Pause recording before sensitive copying. No OCR or claim of perfect password recognition is made. Replayed history is marked to stay out of Windows/cloud clipboard history.
- The full Clipboard history screen provides previews, search, copy, remove, clear, and pause. The tray's Recent clipboard items submenu shows up to 10 saved entries. A busy clipboard is retried asynchronously; the picker pastes only after the requested entry has been restored successfully.
- Implementation references: [Microsoft clipboard privacy formats](https://learn.microsoft.com/en-us/windows/win32/dataxchg/clipboard-formats), [Windows DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata).

## Source setup and exact build commands

Use Python 3.14 x64 on Windows (the build used 3.14). PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe assets/generate_icon.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe twisttype.py
```

Build/package with `powershell -ExecutionPolicy Bypass -File .\build.ps1` (or add `-InstallDependencies` for a fresh setup). The script temporarily restricts PATH to Python and Windows system directories so media tools cannot contribute incompatible ICU/UCRT DLLs. Use this script for a reproducible build. The equivalent PyInstaller invocation **in that clean build environment** is:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --noconsole --noupx --optimize 1 --name TwistType --icon assets/twisttype.ico --add-data "assets/twisttype.ico:assets" --add-data "snippets.yaml:." --add-data "assets/licenses:licenses" --add-data "THIRD-PARTY.md:." --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtPdf --exclude-module tkinter twisttype.py
```

`--onefile` produces a self-contained executable, `--noconsole` hides the console, and `--icon` sets the PE icon. `--add-data` embeds the tray icon and first-run snippet template. `--optimize 1` compiles optimized bytecode; `--noupx` avoids compression-related compatibility issues. Source assets are original; the mark is generated by `assets/generate_icon.py`. Requirements include PySide6 Essentials only; browser/WebEngine components are not needed. Qt/PySide6 is LGPLv3; see `THIRD-PARTY.md` for redistribution notices.

The build creates the clean `release\Single-EXE\TwistType.exe`, the documentation package in `release\TwistType\`, and optional portable/source ZIPs. The portable ZIP does not include a loose snippet file or private history. Rebuilding preserves existing legacy data and AppData. Notices and open-source license texts are also embedded in the executable; Help can open the notices.

CLI checks: `TwistType.exe --smoke-test` renders the editor to `%LOCALAPPDATA%\TwistType\TwistType-preview.png` and exits without installing hooks, recording the clipboard, or changing startup. For isolated QA, set LOCALAPPDATA to a test directory for that process. Normal startup uses hooks; `--background` leaves the editor hidden if the tray is available.

Manual startup registration is available from source (use the UI when running the EXE):

```powershell
.\.venv\Scripts\python.exe -c "import startup; startup.set_enabled(True)"
# Disable:
.\.venv\Scripts\python.exe -c "import startup; startup.set_enabled(False)"
```

## Verification

See `VALIDATION.md` for checks actually performed and limitations. Unit tests exercise matching, exclusions, invalid configuration, persistence, and Unicode injection structures. A local Windows integration harness exercises insertion into its own dedicated edit window and writes no text into your documents.

## 1.0.1 update

Context menus, the tray menu, and the trigger dropdown now specify their own light backgrounds and dark text, including disabled and selected rows. They stay readable when Windows uses a dark palette. Save any draft, quit TwistType from its tray menu, and reopen the updated executable to load the new theme. Updating the executable preserves `snippets.yaml` and does not change startup registration.

## 1.0.2 update

Popup menus now use bright white text on navy, a vivid blue selection, brighter disabled text, and slightly larger, heavier type. The dropdown uses the same colors. The title bar displays the version so you can confirm which build is running. Reopen the app after installing an update; a session already in memory continues using its original theme until restarted.

