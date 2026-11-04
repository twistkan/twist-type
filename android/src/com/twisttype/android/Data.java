package com.twisttype.android;

import android.content.*;
import android.security.keystore.*;
import android.util.AtomicFile;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.util.*;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;

/** App-private snippets plus AES-GCM clipboard history backed by Android Keystore. */
public final class Data {
    private static Data instance;
    public static synchronized Data get(Context c) { if(instance==null) instance=new Data(c.getApplicationContext()); return instance; }
    private final Context context;
    public final SharedPreferences prefs;
    public final List<Logic.Snippet> snippets=new ArrayList<>();
    public final List<String> history=new ArrayList<>();
    public String snippetError="", historyError="";
    public static final Set<String> PASSWORD_PACKAGES=new HashSet<>(Arrays.asList(
        "com.x8bit.bitwarden","com.onepassword.android","com.agilebits.onepassword",
        "keepass2android.keepass2android","keepass2android.keepass2android_nonet",
        "com.kunzisoft.keepass.free","com.kunzisoft.keepass.pro","proton.android.pass",
        "com.lastpass.lpandroid","com.dashlane","com.samsung.android.samsungpass",
        "com.samsung.android.authfw","com.nordpass.android.app.password.manager","com.enpass.app"));

    private Data(Context c) {
        context=c; prefs=c.getSharedPreferences("settings",Context.MODE_PRIVATE);
        try {
            File file=new File(c.getFilesDir(),"snippets.json");
            if(file.exists()) loadSnippets(new String(new AtomicFile(file).readFully(),StandardCharsets.UTF_8));
            else {
                snippets.add(new Logic.Snippet("thanks","Thank you",";thanks","Thank you for your message. I will get back to you soon."));
                snippets.add(new Logic.Snippet("signoff","Simple sign-off",";sig","Kind regards,\nYour name"));
                saveSnippets(new ArrayList<>(snippets));
            }
        } catch(Exception e) { snippetError="Your snippet file could not be opened. It has not been replaced."; snippets.clear(); }
        try { loadHistory(); } catch(Exception e) { history.clear(); historyError="Encrypted history could not be opened. Clear history to start again."; }
    }
    public synchronized void saveSnippets(List<Logic.Snippet> candidate) throws Exception {
        if(!snippetError.isEmpty()) throw new IOException(snippetError);
        Logic.validate(candidate,prefs.getBoolean("immediate",false));
        JSONObject root=new JSONObject(); root.put("version",1);
        JSONArray list=new JSONArray();
        for(Logic.Snippet s:candidate) list.put(new JSONObject().put("id",s.id).put("label",s.label).put("shortcut",s.shortcut).put("text",s.text));
        root.put("snippets",list);
        atomic("snippets.json",root.toString(2).getBytes(StandardCharsets.UTF_8));
        snippets.clear(); snippets.addAll(candidate);
    }
    public synchronized void loadSnippets(String json) throws Exception {
        JSONObject root=new JSONObject(json);
        if(root.optInt("version",-1)!=1) throw new IOException("Unsupported snippet file version.");
        JSONArray list=root.getJSONArray("snippets");
        List<Logic.Snippet> candidate=new ArrayList<>();
        for(int i=0;i<list.length();i++) {
            JSONObject s=list.getJSONObject(i);
            candidate.add(new Logic.Snippet(s.getString("id"),s.getString("label"),s.getString("shortcut"),s.getString("text")));
        }
        Logic.validate(candidate,prefs.getBoolean("immediate",false));
        snippets.clear(); snippets.addAll(candidate);
    }
    public synchronized void importSnippets(String json) throws Exception {
        List<Logic.Snippet> old=new ArrayList<>(snippets);
        String oldError=snippetError; snippetError="";
        try { loadSnippets(json); saveSnippets(new ArrayList<>(snippets)); }
        catch(Exception e) { snippets.clear(); snippets.addAll(old); snippetError=oldError; throw e; }
    }
    public synchronized String exportSnippets() throws Exception {
        JSONObject root=new JSONObject().put("version",1); JSONArray list=new JSONArray();
        for(Logic.Snippet s:snippets) list.put(new JSONObject().put("id",s.id).put("label",s.label).put("shortcut",s.shortcut).put("text",s.text));
        return root.put("snippets",list).toString(2);
    }
    public synchronized boolean addHistory(String value) throws Exception {
        if(!historyError.isEmpty() || value==null || value.trim().isEmpty() || value.length()>32768 || Logic.secret(value,prefs.getBoolean("strict",true))) return false;
        history.remove(value); history.add(0,value);
        while(history.size()>20) history.remove(history.size()-1);
        saveHistory(); return true;
    }
    public synchronized void clearHistory() throws Exception {
        new AtomicFile(new File(context.getFilesDir(),"clipboard.enc")).delete();
        history.clear(); historyError="";
    }
    public synchronized void removeHistory(String value) throws Exception { history.remove(value); saveHistory(); }
    public synchronized void refilter() throws Exception {
        Iterator<String> it=history.iterator();
        while(it.hasNext()) if(Logic.secret(it.next(),prefs.getBoolean("strict",true))) it.remove();
        if(historyError.isEmpty()) saveHistory();
    }
    private SecretKey key() throws Exception {
        KeyStore store=KeyStore.getInstance("AndroidKeyStore"); store.load(null);
        String alias="TwistTypeClipboardV1";
        if(store.containsAlias(alias)) return (SecretKey)store.getKey(alias,null);
        KeyGenerator gen=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
        gen.init(new KeyGenParameterSpec.Builder(alias,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
        return gen.generateKey();
    }
    private void saveHistory() throws Exception {
        if(!historyError.isEmpty()) throw new IOException(historyError);
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding"); cipher.init(Cipher.ENCRYPT_MODE,key());
        byte[] iv=cipher.getIV(), raw=new JSONArray(history).toString().getBytes(StandardCharsets.UTF_8);
        ByteArrayOutputStream output=new ByteArrayOutputStream(); output.write(new byte[]{'T','T','C','L',1,(byte)iv.length});
        output.write(iv); output.write(cipher.doFinal(raw)); atomic("clipboard.enc",output.toByteArray());
    }
    private void loadHistory() throws Exception {
        File file=new File(context.getFilesDir(),"clipboard.enc"); if(!file.exists()) return;
        if(file.length()>4000000) throw new IOException("History too large.");
        byte[] raw=new AtomicFile(file).readFully();
        if(raw.length<34 || raw[0]!='T' || raw[1]!='T' || raw[2]!='C' || raw[3]!='L' || raw[4]!=1 || raw[5]!=12) throw new IOException("Invalid encrypted history.");
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Arrays.copyOfRange(raw,6,18)));
        JSONArray list=new JSONArray(new String(cipher.doFinal(Arrays.copyOfRange(raw,18,raw.length)),StandardCharsets.UTF_8));
        if(list.length()>20) throw new IOException("Invalid history count.");
        for(int i=0;i<list.length();i++) {
            String text=list.getString(i);
            if(text.length()>32768) throw new IOException("History item too large.");
            if(!Logic.secret(text,prefs.getBoolean("strict",true))) history.add(text);
        }
    }
    private void atomic(String name, byte[] bytes) throws Exception {
        AtomicFile file=new AtomicFile(new File(context.getFilesDir(),name)); FileOutputStream stream=null;
        try { stream=file.startWrite(); stream.write(bytes); file.finishWrite(stream); }
        catch(Exception e) { if(stream!=null) file.failWrite(stream); throw e; }
    }
    public boolean excluded(String pkg) {
        if(pkg==null || PASSWORD_PACKAGES.contains(pkg)) return true;
        for(String line:prefs.getString("excluded","").split("\\s+")) if(!line.isEmpty() && line.equals(pkg)) return true;
        return false;
    }
    public static void copy(Context c,String text) {
        ClipData clip=ClipData.newPlainText("TwistType",text);
        android.os.PersistableBundle flags=new android.os.PersistableBundle(); flags.putBoolean("android.content.extra.IS_SENSITIVE",true);
        flags.putBoolean("androidx.core.content.extra.IS_SENSITIVE",true); clip.getDescription().setExtras(flags);
        ((ClipboardManager)c.getSystemService(Context.CLIPBOARD_SERVICE)).setPrimaryClip(clip);
    }
}
