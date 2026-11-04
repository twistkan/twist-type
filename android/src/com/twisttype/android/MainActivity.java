package com.twisttype.android;

import android.app.*;
import android.content.*;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.*;
import android.provider.Settings;
import android.text.*;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public final class MainActivity extends Activity {
    private Data data;
    private LinearLayout host;
    private TextView status;
    private int page=0;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final Runnable pulse=new Runnable(){public void run(){updateStatus();handler.postDelayed(this,1000);}};
    @Override public void onCreate(Bundle saved) { super.onCreate(saved);data=Data.get(this);page=getIntent().getIntExtra("page",0);render(); }
    @Override public void onResume(){super.onResume();handler.post(pulse);}
    @Override public void onPause(){handler.removeCallbacks(pulse);super.onPause();}
    @Override public void onNewIntent(Intent intent){super.onNewIntent(intent);setIntent(intent);page=intent.getIntExtra("page",0);render();}
    private void updateStatus(){if(status!=null)status.setText((ExpandService.instance!=null?"Expansion service connected":"Enable Accessibility for expansion")+"  •  "+(ClipboardService.running?"Clipboard recording":"Clipboard paused"));}
    private void render() {
        LinearLayout root=Ui.column(this);root.setBackgroundColor(Ui.BG);
        LinearLayout header=Ui.card(this,Ui.LAVENDER);
        TextView title=Ui.text(this,"TwistType",29,Ui.PURPLE);title.setTypeface(null,Typeface.BOLD);header.addView(title);
        header.addView(Ui.text(this,"YOUR WORDS, A FEW TAPS AWAY",10,Ui.MUTED));
        status=Ui.text(this,"",12,Ui.MUTED);header.addView(status);root.addView(header);
        host=Ui.column(this);int p=Ui.dp(this,16);host.setPadding(p,p,p,p);
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.addView(host);
        root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout tabs=Ui.row(this);tabs.setBackgroundColor(Ui.LAVENDER);tabs.setPadding(Ui.dp(this,8),Ui.dp(this,6),Ui.dp(this,8),Ui.dp(this,8));
        String[] labels={"Snippets","Clipboard","Settings"};
        for(int i=0;i<labels.length;i++){
            final int next=i;Button b=Ui.button(this,labels[i],v->{page=next;render();},i==page);
            LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,Ui.dp(this,48),1);lp.setMargins(Ui.dp(this,3),0,Ui.dp(this,3),0);tabs.addView(b,lp);
        }
        root.addView(tabs);setContentView(root);
        if(page==0)snippets();else if(page==1)clipboard();else settings();updateStatus();
    }
    private void heading(String text){TextView t=Ui.text(this,text,23,Ui.INK);t.setTypeface(null,Typeface.BOLD);host.addView(t);}
    private void info(String text){host.addView(Ui.text(this,text,14,Ui.MUTED));}
    private void action(String title,View.OnClickListener listener,boolean primary){host.addView(Ui.button(this,title,listener,primary),new LinearLayout.LayoutParams(-1,-2));Ui.gap(host,8);}
    private EditText field(String hint,String value,boolean multiline){
        EditText e=new EditText(this);e.setTextColor(Ui.INK);e.setTextSize(16);e.setHint(hint);e.setText(value);
        e.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS|
            (multiline?android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE:0));
        e.setSingleLine(!multiline);if(multiline){e.setMinLines(4);e.setGravity(Gravity.TOP);}return e;
    }
    private void watch(EditText e,Runnable changed){e.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence s,int st,int c,int a){} public void onTextChanged(CharSequence s,int st,int b,int c){changed.run();}public void afterTextChanged(Editable e){}});}
    private void snippets(){
        heading("Your snippet library");
        LinearLayout summary=Ui.card(this,0xffeaf3fa);summary.addView(Ui.text(this,data.snippets.size()+" saved snippets",23,Ui.INK));
        summary.addView(Ui.text(this,data.prefs.getBoolean("immediate",false)?"Expand immediately":"Type a shortcut, then press Space",14,Ui.MUTED));host.addView(summary);Ui.gap(host,12);
        if(!data.snippetError.isEmpty()) info(data.snippetError);
        action("+ New snippet",v->edit(null),true);
        LinearLayout tools=Ui.row(this);
        Button imp=Ui.button(this,"Import PC JSON",v->pickImport(),false), exp=Ui.button(this,"Export JSON",v->pickExport(),false);
        tools.addView(imp,new LinearLayout.LayoutParams(0,-2,1));tools.addView(exp,new LinearLayout.LayoutParams(0,-2,1));host.addView(tools);
        Ui.gap(host,8);action("Try expansion with your keyboard",v->startActivity(new Intent(this,TestActivity.class)),false);
        EditText search=field("Search names, shortcuts, or text","",false);host.addView(search);
        LinearLayout rows=Ui.column(this);host.addView(rows);
        Runnable refresh=()->{
            rows.removeAllViews();String query=search.getText().toString().toLowerCase(Locale.ROOT);int count=0;
            for(Logic.Snippet s:new ArrayList<>(data.snippets)){
                if(!(s.label+" "+s.shortcut+" "+s.text).toLowerCase(Locale.ROOT).contains(query))continue;
                count++;LinearLayout card=Ui.card(this,Ui.WHITE);
                TextView name=Ui.text(this,s.label,18,Ui.INK);name.setTypeface(null,Typeface.BOLD);card.addView(name);
                card.addView(Ui.text(this,s.shortcut,16,Ui.PURPLE));card.addView(Ui.text(this,Logic.preview(s.text),14,Ui.MUTED));
                LinearLayout buttons=Ui.row(this);
                buttons.addView(Ui.button(this,"Copy",v->{Data.copy(this,s.text);Ui.toast(this,"Snippet copied");},true),new LinearLayout.LayoutParams(0,-2,1));
                buttons.addView(Ui.button(this,"Edit",v->edit(s),false),new LinearLayout.LayoutParams(0,-2,1));
                buttons.addView(Ui.button(this,"Delete",v->new AlertDialog.Builder(this).setTitle("Delete snippet?").setMessage(s.label)
                    .setNegativeButton("Cancel",null).setPositiveButton("Delete",(d,w)->{
                        try{List<Logic.Snippet> list=new ArrayList<>(data.snippets);list.remove(s);data.saveSnippets(list);render();}catch(Exception e){Ui.toast(this,e.getMessage());}
                    }).show(),false),new LinearLayout.LayoutParams(0,-2,1));card.addView(buttons);
                LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.setMargins(0,Ui.dp(this,9),0,0);rows.addView(card,lp);
            }
            if(count==0)rows.addView(Ui.text(this,"No snippets match. Create one or import a library.",15,Ui.MUTED));
        };watch(search,refresh);refresh.run();
    }
    private void edit(Logic.Snippet old){
        LinearLayout form=Ui.column(this);int p=Ui.dp(this,16);form.setPadding(p,0,p,0);
        EditText name=field("Name",old==null?"":old.label,false), shortcut=field("Shortcut, e.g. ;address",old==null?"":old.shortcut,false),
            text=field("Expanded text",old==null?"":old.text,true);
        form.addView(name);form.addView(shortcut);form.addView(text);
        form.addView(Ui.text(this,"Start shortcuts with ; : / ! . or , and avoid spaces. Letter case is ignored: ;sig and ;SIG expand the same snippet.",13,Ui.MUTED));
        ScrollView scroll=new ScrollView(this);scroll.addView(form);
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle(old==null?"New snippet":"Edit snippet").setView(scroll).setNegativeButton("Cancel",null).setPositiveButton("Save",null).create();
        dialog.setOnShowListener(d->dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v->{
            Logic.Snippet next=new Logic.Snippet(old==null?UUID.randomUUID().toString():old.id,name.getText().toString().trim(),shortcut.getText().toString(),text.getText().toString());
            List<Logic.Snippet> list=new ArrayList<>(data.snippets);if(old!=null)list.set(list.indexOf(old),next);else list.add(next);
            try{data.saveSnippets(list);dialog.dismiss();render();}catch(Exception e){Ui.toast(this,e.getMessage());}
        }));dialog.show();
    }
    private void clipboard(){
        heading("Clipboard history");
        LinearLayout summary=Ui.card(this,0xffddf3ee);summary.addView(Ui.text(this,data.history.size()+" / 20 recent copies",23,Ui.INK));
        summary.addView(Ui.text(this,"Stored privately with Android Keystore encryption",13,Ui.MUTED));host.addView(summary);Ui.gap(host,10);
        info(ClipboardService.status);
        if(!data.historyError.isEmpty()) info(data.historyError);
        action(ClipboardService.running?"Pause clipboard recording":"Start clipboard recording",v->toggleRecording(),true);
        action("Open quick clipboard panel",v->{if(ExpandService.instance!=null)ExpandService.instance.showHistory();else Ui.toast(this,"Enable the Accessibility service in Settings first.");},false);
        EditText search=field("Search saved copies","",false);host.addView(search);LinearLayout rows=Ui.column(this);host.addView(rows);
        Runnable refresh=()->{
            rows.removeAllViews();String q=search.getText().toString().toLowerCase(Locale.ROOT);int count=0;
            for(String value:new ArrayList<>(data.history)){
                if(!value.toLowerCase(Locale.ROOT).contains(q))continue;count++;
                LinearLayout card=Ui.card(this,Ui.WHITE);card.addView(Ui.text(this,Logic.preview(value),16,Ui.INK));
                LinearLayout buttons=Ui.row(this);
                buttons.addView(Ui.button(this,"Copy",v->{Data.copy(this,value);Ui.toast(this,"Copied. Switch to your app and paste.");},true),new LinearLayout.LayoutParams(0,-2,1));
                buttons.addView(Ui.button(this,"Preview",v->new AlertDialog.Builder(this).setTitle("Clipboard preview").setMessage(value).setPositiveButton("Close",null).show(),false),new LinearLayout.LayoutParams(0,-2,1));
                buttons.addView(Ui.button(this,"Remove",v->{try{data.removeHistory(value);render();}catch(Exception e){Ui.toast(this,"Could not update encrypted history.");}},false),new LinearLayout.LayoutParams(0,-2,1));card.addView(buttons);
                LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.setMargins(0,Ui.dp(this,9),0,0);rows.addView(card,lp);
            }
            if(count==0)rows.addView(Ui.text(this,"No saved copies. Enable Accessibility, start recording, then copy a normal text phrase in another app.",15,Ui.MUTED));
        };watch(search,refresh);refresh.run();Ui.gap(host,12);
        action("Clear clipboard history",v->new AlertDialog.Builder(this).setTitle("Clear history?").setMessage("Delete all saved clipboard entries? The current system clipboard is left alone.")
            .setNegativeButton("Cancel",null).setPositiveButton("Clear",(d,w)->{try{data.clearHistory();render();}catch(Exception e){Ui.toast(this,"History could not be cleared.");}}).show(),false);
        info("Plain-text history only. Protected and likely-secret copies are omitted. A detector cannot identify every password in ordinary text. Pause recording for sensitive work.");
    }
    private void toggleRecording(){
        if(ClipboardService.running){data.prefs.edit().putBoolean("recording",false).apply();stopService(new Intent(this,ClipboardService.class));}
        else {
            if(Build.VERSION.SDK_INT>=29){Ui.toast(this,"Background clipboard recording in this edition supports Android 8–9.");return;}
            data.prefs.edit().putBoolean("recording",true).apply();startForegroundService(new Intent(this,ClipboardService.class));
        }
        handler.postDelayed(this::render,250);
    }
    private void switcher(String title,String key,boolean defaultValue){
        Switch s=new Switch(this);s.setText(title);s.setTextColor(Ui.INK);s.setPadding(0,Ui.dp(this,10),0,Ui.dp(this,10));s.setChecked(data.prefs.getBoolean(key,defaultValue));
        s.setOnCheckedChangeListener((b,checked)->{
            try {
                if(key.equals("immediate"))Logic.validate(data.snippets,checked);
                data.prefs.edit().putBoolean(key,checked).apply();
                if(key.equals("strict"))data.refilter();
                if(key.equals("bubble") && ExpandService.instance!=null) {
                    if(!checked)ExpandService.instance.closePanel();
                    ExpandService.instance.syncBubble();
                }
            }catch(Exception e){s.setChecked(!checked);Ui.toast(this,e.getMessage());}
        });host.addView(s);
    }
    private void settings(){
        heading("Make it work your way");
        switcher("Show floating TT button on screen","bubble",true);
        info("Turn off to hide TT in other apps. Text expansion keeps working. You can also press and hold TT to hide it; turn it back on here.");
        action("Add clipboard to Quick Settings or side panel",v->new AlertDialog.Builder(this)
            .setTitle("Quick clipboard access")
            .setMessage("Quick Settings: swipe down twice, open the button editor, drag TT Clipboard into your active buttons, then tap Done.\n\nSamsung Apps Edge: open the side panel, go to Apps, tap + or Edit, and choose TT Clipboard. If it is not listed separately, add TwistType and use its Clipboard tab.\n\nTT Clipboard opens recent copies even when the floating TT button is hidden. Enable Accessibility to use the floating panel; otherwise it opens the Clipboard tab. These shortcuts do not start recording.")
            .setPositiveButton("Got it",null).show(),false);
        Ui.gap(host,10);
        LinearLayout welcome=Ui.card(this,0xfffff0e5);
        welcome.addView(Ui.text(this,"Keep your current keyboard",20,Ui.INK));
        welcome.addView(Ui.text(this,"TwistType uses Android's Accessibility service to expand shortcuts in supported editable fields. It reads the focused field to do this. Password fields and excluded apps are skipped. No network permission is included.",14,Ui.MUTED));host.addView(welcome);Ui.gap(host,10);
        action("Enable Accessibility service",v->startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)),true);
        action("Try a shortcut",v->startActivity(new Intent(this,TestActivity.class)),false);
        switcher("Expand shortcuts","expansion",true);
        switcher("Expand immediately (otherwise Space/Tab)","immediate",false);
        switcher("Keep Space after expansion","keep_space",true);
        info("Shortcuts ignore letter case. Expanded text keeps the capitalization you saved.");
        Ui.gap(host,10);heading("Clipboard privacy");
        switcher("Hide single-word copies too (safer)","strict",true);
        action(ClipboardService.running?"Pause clipboard recording":"Start clipboard recording",v->toggleRecording(),false);
        info("Recording is opt-in and shows a persistent notification. On Android 9 it can capture new text copies in other apps while the Accessibility service identifies the focused context. Nothing is imported from the existing clipboard on startup.");
        info("Password-manager packages, identifiable password fields, source sensitivity flags, token/private-key patterns, and likely secrets are omitted. Multiword passphrases can look like normal text; no automatic password filter is perfect.");
        Ui.gap(host,10);heading("Additional excluded apps");
        info("Enter Android package names, one per line (for example com.example.app). Password-manager exclusions always apply.");
        EditText excluded=field("Package names",data.prefs.getString("excluded",""),true);host.addView(excluded);
        action("Save excluded apps",v->{String value=excluded.getText().toString().trim();if(value.length()>6000){Ui.toast(this,"Exclusion list is too long.");return;}
            for(String line:value.split("\\s+"))if(!line.isEmpty() && !line.matches("[A-Za-z0-9_]+(\\.[A-Za-z0-9_]+)+")){Ui.toast(this,"Enter package names separated by new lines.");return;}
            data.prefs.edit().putString("excluded",value).apply();Ui.toast(this,"Exclusions saved");},false);
        Ui.gap(host,12);heading("About this edition");
        info("TwistType Android 1.0.2 • Personal offline edition\nDesigned for Android 9 on Galaxy Note8. English plain-text snippets; no autocorrect/dictionary replacement. Some custom editors do not expose accessible editable fields; use Copy instead. Very large fields over 20,000 characters are skipped. The floating clipboard panel works through Accessibility; with an external keyboard, Ctrl+Alt+V also opens it.");
        info("Use Import PC JSON for a file generated by the included PC export tool. Libraries replace after confirmation. Clipboard history is not exported or synced. Snippets stay in private app storage, history is encrypted, and Android backup is disabled. Uninstalling the app removes its private data and encryption key.");
    }
    private void pickImport(){Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");startActivityForResult(i,31);}
    private void pickExport(){Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/json").putExtra(Intent.EXTRA_TITLE,"TwistType-snippets.json");startActivityForResult(i,32);}
    @Override public void onActivityResult(int request,int result,Intent intent){
        super.onActivityResult(request,result,intent);if(result!=RESULT_OK || intent==null || intent.getData()==null)return;Uri uri=intent.getData();
        if(request==32){try(OutputStream out=getContentResolver().openOutputStream(uri,"wt")){if(out==null)throw new IOException();out.write(data.exportSnippets().getBytes(StandardCharsets.UTF_8));Ui.toast(this,"Snippet library exported");}catch(Exception e){Ui.toast(this,"Could not export the library.");}}
        if(request==31){
            try(InputStream input=getContentResolver().openInputStream(uri);ByteArrayOutputStream output=new ByteArrayOutputStream()){
                if(input==null)throw new IOException();byte[] buffer=new byte[8192];int count;
                while((count=input.read(buffer))!=-1){output.write(buffer,0,count);if(output.size()>2000000)throw new IOException("Import is larger than 2 MB.");}
                String json=new String(output.toByteArray(),StandardCharsets.UTF_8);JSONObject parsed=new JSONObject(json);int total=parsed.getJSONArray("snippets").length();
                new AlertDialog.Builder(this).setTitle("Replace snippet library?").setMessage("Import "+total+" snippets? Your existing Android library will be replaced. Clipboard history stays separate.")
                    .setNegativeButton("Cancel",null).setPositiveButton("Import",(d,w)->{try{data.importSnippets(json);page=0;render();Ui.toast(this,"Library imported");}catch(Exception e){Ui.toast(this,e.getMessage());}}).show();
            }catch(Exception e){Ui.toast(this,"Import failed. Choose a valid TwistType JSON export, maximum 2 MB.");}
        }
    }
    @Override public void onBackPressed(){if(page!=0){page=0;render();}else super.onBackPressed();}
}
