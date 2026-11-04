package com.twisttype.android;

import android.content.Intent;
import android.service.quicksettings.Tile;
import android.service.quicksettings.TileService;

/** A launch action, not a recording toggle; never reads clipboard contents. */
public final class ClipboardTileService extends TileService {
    @Override public void onStartListening() {
        Tile tile=getQsTile();
        if(tile!=null) {
            tile.setLabel("TT Clipboard");
            tile.setState(Tile.STATE_INACTIVE);
            tile.updateTile();
        }
    }
    @Override public void onClick() {
        super.onClick();
        if(isLocked()) unlockAndRun(this::openClipboard);
        else openClipboard();
    }
    private void openClipboard() {
        // This personal Android 8-9 edition uses the API available on that phone.
        startActivityAndCollapse(new Intent(this,ClipboardEntryActivity.class)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TOP));
    }
}
