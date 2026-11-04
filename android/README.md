# TwistType Android 1.0.2 — Galaxy Note8 / Android 9

A native, offline Android app that keeps Samsung Keyboard or Gboard. It includes a snippet editor, Space/Tab or immediate expansion, encrypted 20-entry plain-text clipboard history, search, app exclusions, and a floating TT clipboard panel. There are no ads, analytics, accounts, or INTERNET permission. It uses the same lavender/indigo visual direction as the desktop app.

## Update from 1.0.0 or 1.0.1

Install the 1.0.2 APK over the existing app; do not uninstall first. The package and signing key are unchanged, so snippets, encrypted history, and preferences stay in place. No JSON reimport is needed.

Shortcuts now ignore letter case in both trigger modes; inserted text keeps its saved capitalization. Case-only duplicates and overlapping immediate shortcuts are rejected when saving/importing.

In Settings, the first switch is **Show floating TT button on screen**. Turn it off to hide the overlay while keeping expansion active. Press and hold TT to hide it directly from another app; use the Settings switch to show it again. The app's Clipboard tab remains available when hidden.

## Quick Settings and Samsung Apps Edge

The update adds a **TT Clipboard** Quick Settings tile and a second launcher icon named **TT Clipboard**. Both open the floating history panel when Accessibility is connected, even if the TT bubble is hidden. With no Accessibility connection, they open the app's Clipboard tab for Copy/manual Paste. Opening either entry does not start recording or enable the bubble. The tile shows a generic icon/label, with no clipboard text, and requests unlock before showing history when locked.

- **Quick Settings:** swipe down twice, open the three-dot menu and choose Button order (or Edit buttons), then drag **TT Clipboard** from available buttons into the active grid and tap Done. Samsung's exact menu wording varies. The tile may be on another page of available buttons.
- **Samsung Apps Edge:** swipe in the Edge handle, find Apps, tap **+** or **Edit**, select **TT Clipboard**, then finish editing. If Apps is disabled, enable it under Settings > Display > Edge screen > Edge panels. This is a launcher shortcut into TwistType, not a dedicated Samsung clipboard-content panel. Some Samsung versions may group launcher entries by app: if the separate entry is absent, add TwistType and open its Clipboard tab instead. The Note8's actual list still needs confirmation on the phone.
- **Home screen:** TT Clipboard also appears in the app drawer and can be dragged onto the home screen.

Samsung's Apps Edge supports adding apps: https://www.samsung.com/uk/support/mobile-devices/what-is-the-edge-panel-and-how-do-i-use-it/
Android tile API: https://developer.android.com/develop/ui/views/quicksettings-tiles

## Install on your Note8

1. Copy `TwistType-Android-1.0.2.apk` to the phone (USB, local file transfer, etc.) and open it in My Files. Android may ask you to allow installation from that app; make that choice yourself if you want to install this local build.
2. Open TwistType. In Settings, tap **Enable Accessibility service**. Find **TwistType text expansion**, review Android's disclosure, and enable it yourself. This allows the app to inspect the focused editable field and insert your chosen snippets. It does not replace your keyboard.
3. Tap **Try a shortcut**. Type `;thanks` followed by Space. Customize the sample sign-off before using it. Immediate mode is optional in Settings.
4. To remember copies, tap **Start clipboard recording**. A persistent notification gives you a visible recording indicator and Pause control. Accessibility must be connected so sensitive contexts can be identified. Existing clipboard contents are not imported on startup.
5. Tap the small floating **TT** button from another app to open recent copies; tap an entry to paste into the previously focused editable field. If the field cannot be safely reached, the text is copied for manual pasting. Drag the TT button vertically to reposition it. Turn it off in Settings if you prefer using the app/notification. With an external physical keyboard, Ctrl+Alt+V opens the panel; Escape closes it.

Accessibility and installation permissions are user-controlled. The app never enables them silently. Clipboard recording is off until you explicitly start it.

## Bring your PC snippets over

On the PC, run from the TextPanda project:

```powershell
.\.venv\Scripts\python.exe android\export_desktop.py
```

This creates `release\Android\TwistType-PC-snippets.json` from your current AppData library. Copy that JSON to your phone, tap **Import PC JSON**, choose it, and confirm replacement. Names, shortcuts, and text are preserved. Clipboard history and PC-only settings are not exported. The Android app can also export its own JSON library using Android's file picker. It does not directly read YAML.

## Privacy and compatibility

- Designed for the user's Android 9 Note8; minimum Android 8/API26. This is a universal DEX APK with no CPU-specific native library. Background clipboard capture is intentionally disabled on Android 10+; it does not bypass newer Android privacy restrictions.
- Snippets are in app-private JSON storage. Clipboard history is AES-GCM encrypted with an Android Keystore key, limited to 20 distinct text entries of up to 32,768 UTF-16 units. No clipboard images/files or rich formatting in this first Android edition. App data is not backed up through Android; uninstalling removes the data and key. Export important snippets separately.
- Password-manager packages and user-excluded packages are skipped. Identifiable password fields, source-app sensitive clipboard flags, common secret/token/private-key patterns, likely OTPs, and single-token copies are omitted. Single-token filtering is on by default and can be relaxed; other protections remain. The app cannot reliably identify every unmarked password or multiword passphrase. Pause recording before sensitive copying. No password contents are written to logs.
- Android 9 does not provide a public clipboard-owner API. The Accessibility service checks the active/focused context before recording a new copy; background source attribution cannot be guaranteed. This is conservative filtering, not a password vault or perfect DLP.
- Expansion uses Android's public Accessibility ACTION_SET_TEXT / ACTION_SET_SELECTION; some custom editors, web fields, composing/autocorrect behavior, and apps that do not expose editable accessibility nodes will not support automatic expansion. Copy from the snippet library works as a fallback. Password fields are never expanded into. Fields over 20,000 characters and pasted/multi-character insertions are skipped to avoid broad document rewrites.
- A text change is matched only for a single inserted character. Immediate mode rejects overlapping shortcut prefixes. Shortcuts ignore letter case and are 2–40-character ASCII tokens starting with `; : / ! . ,`. Space is preserved by default; Tab triggers without being retained. Newline alone is not a trigger.
- The overlay uses Accessibility's overlay window type; it does not request separate "draw over other apps" permission. It is hidden while the device is locked. No root, phone storage scan, contacts, camera, microphone, or location permission is requested.
- Samsung's battery restrictions may stop background components. If that occurs, reopen TwistType and inspect service/recording status; use Samsung's app battery settings yourself if desired. There is no boot auto-start in this first release.

## Build and source

`android/build.ps1` builds native Java/resources directly with JDK21, Android platform 35, and Android build tools (aapt2, D8, zipalign, apksigner). No Gradle download or third-party app dependency is required. The build targets API28 for this personal Android9 APK. By default it reads an existing, local toolchain in the sibling `MobileTrans App\tools` directory, without modifying it. On another PC supply paths:

```powershell
powershell -ExecutionPolicy Bypass -File android\build.ps1 -JavaHome C:\path\to\jdk-21 -AndroidJar C:\Android\platforms\android-35\android.jar -BuildTools C:\Android\build-tools\35.0.0
```

Keep `android/signing` private and backed up; it contains this app's signing key/password and is required for compatible future updates. It is excluded from source archives. Core matching/privacy tests run on the JVM before packaging. See `android/VALIDATION.md` for actual checks and what has not been tested. No APK is installed onto a phone automatically.

Public API references: Android AccessibilityService and AccessibilityNodeInfo, ClipboardManager/ClipDescription, Android Keystore, AtomicFile, foreground services, and InputMethod/clipboard privacy documentation on developer.android.com. Source is original; the T icon is an original adaptation of TwistType's mark. The reference design contributes colors/layout direction only.
