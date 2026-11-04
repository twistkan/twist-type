# Android implementation scope

Confirmed: Galaxy Note8, Android 9, retain the user's existing keyboard. Native Java Views with min API26, target API28, compiled against platform35. APK for direct personal installation, not a Play Store submission. No server, auth, payments, networking, or database service.

- MainActivity: library/editor, clipboard preview/search, explicit setup/settings, JSON interchange.
- ExpandService: public Accessibility API for focused editable fields, password/exclusion guard, one-character matching, caret restoration, optional Accessibility overlay and external-keyboard hotkey.
- ClipboardService: opt-in visible foreground service, new text copies only on Android8–9; context/flag/content checks before history insertion.
- Data: validated AtomicFile snippet JSON, private SharedPreferences, 20-item clipboard list encrypted AES-GCM through Android Keystore; no backup/export of clipboard history.
- Logic: platform-independent matcher, shortcut validation, secret filter; JVM test harness.
- ClipboardTileService: system-bound Quick Settings launch action, protected by BIND_QUICK_SETTINGS_TILE; unlock before launch, no history reads in the tile.
- ClipboardEntryActivity: transparent TT Clipboard launcher for Apps Edge/home screen and the tile. Finishes before opening the Accessibility overlay so the prior editor can regain focus; falls back to MainActivity Clipboard tab without Accessibility. Does not change recording/bubble preferences.
- TestActivity: focused local field for safe first-device verification.

The clipboard panel uses a non-focusable Accessibility overlay to preserve the original target; ACTION_PASTE is attempted only on a refreshed editable, non-password field in the active window. Failure leaves the selected text copied for manual Paste. No hidden permission granting, root, or private OS APIs. Accessibility source context cannot establish the original owner of every background clipboard change on Android9, and password filtering cannot identify all unmarked passphrases. Those limits are disclosed in app and README.

Existing Windows source/data are not changed by the Android build. Toolchain reuse is read-only. Private signing material and any optional user snippet export are omitted from the distributable source archive.
