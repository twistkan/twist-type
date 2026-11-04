package com.twisttype.android;

import android.accessibilityservice.AccessibilityService;
import android.app.KeyguardManager;
import android.content.*;
import android.graphics.PixelFormat;
import android.os.*;
import android.view.*;
import android.view.accessibility.*;
import android.widget.*;
import java.util.*;

public final class ExpandService extends AccessibilityService {
    public static ExpandService instance;
    private WindowManager manager;
    private View bubble, panel;
    private AccessibilityNodeInfo pasteTarget;
    private Data data;
    private String lastWritten="", lastWrittenNode="";
    private int lastWindow=-1;
    private final Handler handler=new Handler(Looper.getMainLooper());

    @Override protected void onServiceConnected() {
        instance=this; data=Data.get(this); manager=(WindowManager)getSystemService(WINDOW_SERVICE); syncBubble();
    }
    public boolean locked() { return ((KeyguardManager)getSystemService(KEYGUARD_SERVICE)).isKeyguardLocked(); }
    /** Best-effort focused-window context, read before clipboard text. */
    public String safeContext() {
        if(locked()) return null;
        AccessibilityNodeInfo root=getRootInActiveWindow();
        if(root==null) return null;
        AccessibilityNodeInfo focus=null;
        try {
            String pkg=root.getPackageName()==null?null:root.getPackageName().toString();
            if(data.excluded(pkg)) return null;
            focus=root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
            if(focus!=null && focus.isPassword()) return null;
            return pkg;
        } finally { if(focus!=null) focus.recycle(); root.recycle(); }
    }
    @Override public void onAccessibilityEvent(AccessibilityEvent event) {
        if(data==null) return;
        if(event.getEventType()==AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) {
            lastWritten=""; lastWrittenNode=""; syncBubble();
        }
        if(event.getEventType()!=AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED || locked() || event.isPassword()
            || !data.prefs.getBoolean("expansion",true) || !data.snippetError.isEmpty()) return;
        String pkg=event.getPackageName()==null?null:event.getPackageName().toString();
        if(data.excluded(pkg)) return;
        AccessibilityNodeInfo node=event.getSource(); if(node==null) return;
        try {
            if(node.isPassword() || !node.isEditable() || !node.isFocused()) return;
            String viewId=node.getViewIdResourceName();
            boolean test=getPackageName().equals(pkg) && (getPackageName()+":id/test_field").equals(viewId);
            if(getPackageName().equals(pkg) && !test) return;
            CharSequence current=node.getText(); if(current==null || current.length()>20000) return;
            String after=current.toString();
            String signature=node.getWindowId()+":"+viewId;
            if(signature.equals(lastWrittenNode) && after.equals(lastWritten)) return;
            int cursor=node.getTextSelectionEnd();
            if(cursor<0 || node.getTextSelectionStart()!=cursor) return;
            String before=event.getBeforeText()==null?null:event.getBeforeText().toString();
            Logic.Replacement result=Logic.expand(before,after,cursor,new ArrayList<>(data.snippets),
                data.prefs.getBoolean("immediate",false),data.prefs.getBoolean("keep_space",true));
            if(result==null || !node.refresh() || node.getText()==null || !after.contentEquals(node.getText())
                || node.isPassword() || !node.isFocused() || node.getTextSelectionEnd()!=cursor) return;
            Bundle args=new Bundle(); args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,result.text);
            lastWritten=result.text; lastWrittenNode=signature;
            if(node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT,args)) {
                Bundle selection=new Bundle(); selection.putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_START_INT,result.cursor);
                selection.putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_END_INT,result.cursor);
                node.performAction(AccessibilityNodeInfo.ACTION_SET_SELECTION,selection);
            } else { lastWritten=""; lastWrittenNode=""; }
        } catch(RuntimeException ignored) { lastWritten=""; lastWrittenNode=""; }
        finally { node.recycle(); }
    }
    public void syncBubble() {
        if(manager==null) return;
        boolean deviceLocked=locked();
        boolean show=data.prefs.getBoolean("bubble",true) && !deviceLocked;
        // Hiding the shortcut must not close history opened by the tile/Edge entry.
        if(!show) { removeBubble(); if(deviceLocked) closePanel(); return; }
        if(bubble!=null) return;
        TextView button=Ui.text(this,"TT",17,Ui.WHITE); button.setGravity(Gravity.CENTER); button.setTypeface(null,1);
        button.setBackground(Ui.round(Ui.PURPLE,26)); button.setContentDescription("Open TwistType clipboard history");
        WindowManager.LayoutParams params=new WindowManager.LayoutParams(Ui.dp(this,48),Ui.dp(this,48),
            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE|WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,PixelFormat.TRANSLUCENT);
        params.gravity=Gravity.RIGHT|Gravity.CENTER_VERTICAL; params.x=Ui.dp(this,8); params.y=Ui.dp(this,100);
        button.setOnClickListener(v->showHistory());
        button.setOnLongClickListener(v->{
            data.prefs.edit().putBoolean("bubble",false).apply(); closePanel(); syncBubble();
            Ui.toast(this,"TT hidden. Show it again in TwistType Settings."); return true;
        });
        button.setOnTouchListener(new View.OnTouchListener(){
            float y; int start; boolean moved, held;
            final Runnable hold=()->{ held=true; button.performLongClick(); };
            public boolean onTouch(View v,MotionEvent e) {
                if(e.getAction()==MotionEvent.ACTION_DOWN) { y=e.getRawY(); start=params.y; moved=false; held=false; handler.postDelayed(hold,ViewConfiguration.getLongPressTimeout()); return true; }
                if(e.getAction()==MotionEvent.ACTION_MOVE) {
                    if(held) return true;
                    int delta=(int)(e.getRawY()-y); if(Math.abs(delta)>Ui.dp(ExpandService.this,7)) { moved=true; handler.removeCallbacks(hold); }
                    if(moved) { params.y=Math.max(-600,Math.min(600,start+delta)); try { manager.updateViewLayout(v,params); } catch(RuntimeException ignored){} }
                    return true;
                }
                if(e.getAction()==MotionEvent.ACTION_UP) { handler.removeCallbacks(hold); if(!moved && !held) v.performClick(); return true; }
                if(e.getAction()==MotionEvent.ACTION_CANCEL) handler.removeCallbacks(hold);
                return true;
            }
        });
        try { manager.addView(button,params); bubble=button; } catch(RuntimeException ignored){}
    }
    private void rememberTarget() {
        if(pasteTarget!=null) { pasteTarget.recycle(); pasteTarget=null; }
        AccessibilityNodeInfo root=getRootInActiveWindow(); if(root==null) return;
        try {
            AccessibilityNodeInfo focus=root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
            if(focus!=null) {
                String pkg=focus.getPackageName()==null?null:focus.getPackageName().toString();
                if(!focus.isPassword() && focus.isEditable() && !data.excluded(pkg)) pasteTarget=AccessibilityNodeInfo.obtain(focus);
                focus.recycle();
            }
        } finally { root.recycle(); }
    }
    public void showHistory() {
        if(locked()) return;
        if(panel!=null) { closePanel(); return; }
        rememberTarget();
        LinearLayout box=Ui.column(this); box.setPadding(Ui.dp(this,16),Ui.dp(this,16),Ui.dp(this,16),Ui.dp(this,12));
        box.setBackground(Ui.round(Ui.NAVY,16));
        LinearLayout head=Ui.row(this);
        TextView title=Ui.text(this,"Recent copies",20,Ui.WHITE); head.addView(title,new LinearLayout.LayoutParams(0,-2,1));
        Button dismiss=Ui.button(this,"Close",v->closePanel(),false); head.addView(dismiss); box.addView(head);
        TextView hint=Ui.text(this,"Tap to copy and paste • 20 text entries",12,0xffc2c9e2); box.addView(hint);
        ScrollView scroll=new ScrollView(this); LinearLayout list=Ui.column(this);
        List<String> entries=new ArrayList<>(data.history);
        if(!data.historyError.isEmpty()) list.addView(Ui.text(this,data.historyError,14,Ui.WHITE));
        else if(entries.isEmpty()) list.addView(Ui.text(this,"No saved copies yet. Enable clipboard recording in TwistType.",15,Ui.WHITE));
        for(String value:entries) {
            TextView item=Ui.text(this,Logic.preview(value),15,Ui.WHITE); int p=Ui.dp(this,13); item.setPadding(p,p,p,p);
            item.setBackground(Ui.selector(Ui.NAVY,Ui.BLUE)); item.setContentDescription("Paste clipboard entry: "+Logic.preview(value));
            item.setOnClickListener(v->paste(value)); list.addView(item,new LinearLayout.LayoutParams(-1,-2));
        }
        scroll.addView(list); box.addView(scroll,new LinearLayout.LayoutParams(-1,Ui.dp(this,Math.min(340,Math.max(110,entries.size()*56)))));
        WindowManager.LayoutParams params=new WindowManager.LayoutParams(
            Math.min(getResources().getDisplayMetrics().widthPixels-Ui.dp(this,24),Ui.dp(this,380)),-2,
            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE|WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,PixelFormat.TRANSLUCENT);
        params.gravity=Gravity.CENTER;
        try { manager.addView(box,params); panel=box; } catch(RuntimeException ignored){closePanel();}
    }
    private void paste(String value) {
        closePanelView();
        try { Data.copy(this,value); } catch(RuntimeException e) { Ui.toast(this,"Clipboard is busy. Try again."); return; }
        AccessibilityNodeInfo target=pasteTarget; pasteTarget=null;
        handler.postDelayed(()->{
            boolean pasted=false;
            try {
                if(target!=null && !locked() && target.refresh() && target.isEditable() && target.isFocused() && !target.isPassword()) {
                    String pkg=target.getPackageName()==null?null:target.getPackageName().toString();
                    AccessibilityNodeInfo root=getRootInActiveWindow();
                    try {
                        if(root!=null && root.getWindowId()==target.getWindowId() && !data.excluded(pkg))
                            pasted=target.performAction(AccessibilityNodeInfo.ACTION_PASTE);
                    } finally { if(root!=null) root.recycle(); }
                }
            } catch(RuntimeException ignored){}
            finally { if(target!=null) target.recycle(); }
            if(!pasted) Ui.toast(this,"Copied. Tap the desired field and choose Paste.");
        },100);
    }
    private void closePanelView() { if(panel!=null) { try{manager.removeView(panel);}catch(RuntimeException ignored){} panel=null; } }
    public void closePanel() { closePanelView(); if(pasteTarget!=null){pasteTarget.recycle();pasteTarget=null;} }
    private void removeBubble() { if(bubble!=null) { try{manager.removeView(bubble);}catch(RuntimeException ignored){} bubble=null; } }
    @Override protected boolean onKeyEvent(KeyEvent event) {
        if(event.getKeyCode()==KeyEvent.KEYCODE_V && event.isCtrlPressed() && event.isAltPressed()) {
            if(event.getAction()==KeyEvent.ACTION_DOWN && event.getRepeatCount()==0) showHistory(); return true;
        }
        if(event.getKeyCode()==KeyEvent.KEYCODE_ESCAPE && panel!=null) { if(event.getAction()==KeyEvent.ACTION_DOWN) closePanel(); return true; }
        return false;
    }
    @Override public void onInterrupt() { closePanel(); }
    @Override public void onDestroy() { removeBubble(); closePanel(); if(instance==this) instance=null; super.onDestroy(); }
}
