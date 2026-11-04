package com.twisttype.android;

import android.app.Activity;
import android.app.KeyguardManager;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;

/** Shared entry for Quick Settings and the launcher/Apps Edge shortcut. */
public final class ClipboardEntryActivity extends Activity {
    private boolean opened, waitingForUnlock;
    @Override public void onCreate(Bundle saved) { super.onCreate(saved); }
    @Override protected void onResume() {
        super.onResume();
        if(opened || waitingForUnlock) return;
        KeyguardManager guard=(KeyguardManager)getSystemService(KEYGUARD_SERVICE);
        if(guard.isKeyguardLocked()) {
            waitingForUnlock=true;
            guard.requestDismissKeyguard(this,new KeyguardManager.KeyguardDismissCallback(){
                @Override public void onDismissSucceeded(){waitingForUnlock=false;openClipboard();}
                @Override public void onDismissCancelled(){finish();}
                @Override public void onDismissError(){finish();}
            });
        } else openClipboard();
    }
    private void openClipboard() {
        if(opened || isFinishing() || isDestroyed()) return;
        KeyguardManager guard=(KeyguardManager)getSystemService(KEYGUARD_SERVICE);
        if(guard.isKeyguardLocked()) { finish(); return; }
        opened=true;
        if(ExpandService.instance==null) {
            openLibrary(); finish(); return;
        }
        // Finish this transparent entry first so the previous editor regains focus.
        // The overlay independently checks the lock and revalidates paste targets.
        finish();
        final android.content.Context app=getApplicationContext();
        new Handler(Looper.getMainLooper()).postDelayed(()->{
            if(((KeyguardManager)app.getSystemService(KEYGUARD_SERVICE)).isKeyguardLocked()) return;
            ExpandService access=ExpandService.instance;
            if(access!=null) { access.closePanel(); access.showHistory(); }
            else app.startActivity(new Intent(app,MainActivity.class).putExtra("page",1)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TOP|Intent.FLAG_ACTIVITY_SINGLE_TOP));
        },300);
    }
    private void openLibrary() {
        startActivity(new Intent(this,MainActivity.class).putExtra("page",1)
            .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP|Intent.FLAG_ACTIVITY_SINGLE_TOP));
    }
}
