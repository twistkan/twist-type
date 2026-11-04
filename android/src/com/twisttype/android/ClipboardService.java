package com.twisttype.android;

import android.app.*;
import android.content.*;
import android.os.*;

public final class ClipboardService extends Service implements ClipboardManager.OnPrimaryClipChangedListener {
    public static boolean running=false;
    public static String status="Recording is off";
    private ClipboardManager clipboard;
    private Data data;
    private final Handler handler=new Handler(Looper.getMainLooper());
    @Override public void onCreate() {
        super.onCreate(); data=Data.get(this); clipboard=(ClipboardManager)getSystemService(CLIPBOARD_SERVICE);
        NotificationChannel channel=new NotificationChannel("clipboard","Clipboard recording",NotificationManager.IMPORTANCE_LOW);
        channel.setDescription("Visible control for offline clipboard history.");
        ((NotificationManager)getSystemService(NOTIFICATION_SERVICE)).createNotificationChannel(channel);
        Intent open=new Intent(this,MainActivity.class).putExtra("page",1);
        PendingIntent pending=PendingIntent.getActivity(this,1,open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        PendingIntent stop=PendingIntent.getService(this,2,new Intent(this,ClipboardService.class).setAction("STOP"),PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        Notification notification=new Notification.Builder(this,"clipboard").setSmallIcon(R.drawable.ic_notification)
            .setContentTitle("TwistType clipboard history").setContentText("Recording new text copies locally • Tap to view")
            .setContentIntent(pending).setOngoing(true).addAction(new Notification.Action.Builder(null,"Pause",stop).build()).build();
        startForeground(21,notification); running=true; status="Recording new copies";
        clipboard.addPrimaryClipChangedListener(this); // Never imports the pre-existing clipboard.
    }
    @Override public int onStartCommand(Intent intent,int flags,int startId) {
        if(intent!=null && "STOP".equals(intent.getAction())) { data.prefs.edit().putBoolean("recording",false).apply(); stopSelf(); return START_NOT_STICKY; }
        return START_STICKY;
    }
    @Override public void onPrimaryClipChanged() { handler.post(this::capture); }
    private void capture() {
        if(!running || !data.prefs.getBoolean("recording",false) || !data.historyError.isEmpty()) return;
        // Android 10+ disallows general background clipboard reads. This release
        // intentionally targets the user's Android 9 phone, without workarounds.
        if(Build.VERSION.SDK_INT>=29) { status="Background history requires Android 8–9"; return; }
        ExpandService access=ExpandService.instance;
        if(access==null || access.safeContext()==null) { status="Sensitive or unidentified copy omitted"; return; }
        try {
            ClipDescription desc=clipboard.getPrimaryClipDescription();
            if(desc==null) return;
            PersistableBundle extras=desc.getExtras();
            if(extras!=null && (extras.getBoolean("android.content.extra.IS_SENSITIVE",false)
                || extras.getBoolean("androidx.core.content.extra.IS_SENSITIVE",false))) { status="Protected copy omitted"; return; }
            ClipData clip=clipboard.getPrimaryClip();
            if(clip==null || clip.getItemCount()<1 || clip.getItemAt(0).getText()==null) return;
            String value=clip.getItemAt(0).getText().toString();
            status=data.addHistory(value)?"Saved with local encryption":"Potentially sensitive copy omitted";
        } catch(Exception e) { status="This copy could not be saved safely"; }
    }
    @Override public void onDestroy() {
        running=false; status="Recording is off"; handler.removeCallbacksAndMessages(null);
        if(clipboard!=null) clipboard.removePrimaryClipChangedListener(this);
        stopForeground(true); super.onDestroy();
    }
    @Override public android.os.IBinder onBind(Intent intent) { return null; }
}
