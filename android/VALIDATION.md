# TwistType Android 1.0.2 - validation, 2026-11-04

## Changes

- TT Clipboard Quick Settings tile: public TileService, exported with the system BIND_QUICK_SETTINGS_TILE binding permission, generic label/icon, no history content in the tile, unlock before opening on a locked device.
- TT Clipboard launcher activity: a separate app-drawer entry suitable for Samsung Apps Edge or home-screen launch. This is a shortcut, not a Samsung-specific content panel. Actual Samsung picker behavior still requires a phone check; some launchers may group entries by package.
- Shared transparent entry finishes before showing the Accessibility history overlay to let the prior editor regain focus. Paste still refreshes and verifies the focused non-password target. Without Accessibility it opens the Clipboard tab for manual Copy/Paste. Rechecks lock state before opening history.
- Tile and launcher do not change recording or bubble preferences. Hidden-bubble window updates no longer dismiss a panel opened from Quick Settings/Edge. Explicitly hiding the bubble closes the existing panel; lockscreen updates continue to dismiss it.
- In-app setup instructions in Settings. Original case-insensitive shortcuts, snippet storage, history encryption and recording opt-in remain in place.

## Validation

33 existing JVM matching/privacy checks pass. Package checks include the new tile service binding, discoverable exported launcher with icon/theme and exclusion from Recents, both launcher filters, packaged icons, version/SDK, unchanged requested permissions, Android 9 signature verification, alignment and signing-certificate match against 1.0.0.

All 15 package checks passed. APK: 45,851 bytes. SHA256: `a8d525c512f96210935c19b12c03e5e946eac2c038c14e633efa623d60cd1d5a`.

No physical device was connected to ADB. This update has not been installed or run on the Note8 by the agent. Source/build/package checks cannot confirm Samsung UI behavior, launch timing, previous-editor focus or device unlock behavior. They are not Play Protect approval.

## Phone acceptance checks

1. Install 1.0.2 over the current app without uninstalling. Confirm saved snippets/history/preferences survive.
2. In Quick Settings button order, locate TT Clipboard, add it, tap Done and open it. Confirm the shade collapses and saved history appears. Tap a normal entry in an accessible editor; if automatic paste is unavailable, use manual Paste.
3. Turn the TT bubble off in Settings. Repeat tile launch. History must stay open despite window-state events. Recording and expansion preferences must not change.
4. In Samsung Apps Edge (+/Edit), add TT Clipboard. If Samsung groups entries, add TwistType and open the Clipboard tab. Test the new app-drawer icon and home-screen shortcut too.
5. Disable Accessibility manually and launch the tile/icon: it should open the Clipboard tab without starting recording. Restore Accessibility for normal expansion afterward if desired.
6. Lock the phone and try the tile: history must require unlock. Cancel unlock: no contents should appear. Unlock successfully: history may open. Lock again while the panel is showing: history should dismiss.
7. Verify the original TwistType icon still opens normally, Back returns to the prior app after the floating panel closes, and repeated clipboard-entry taps open the panel rather than duplicating it. Confirm upper/lower/mixed-case expansions still work.

## Scope

Same package com.twisttype.android, version code 3; minimum API26, target API28 for this personal Android9 edition. No new uses-permission declarations, network access, Samsung SDK dependency, private APIs, automatic tile insertion, or automatic side-panel configuration. The user adds the tile/shortcut themselves.
