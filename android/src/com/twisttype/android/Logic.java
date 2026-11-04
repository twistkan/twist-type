package com.twisttype.android;

import java.net.URI;
import java.util.*;
import java.util.regex.Pattern;

/** Pure-Java matching and privacy rules; independently runnable JVM tests. */
public final class Logic {
    public static final class Snippet {
        public final String id, label, shortcut, text;
        public Snippet(String id, String label, String shortcut, String text) {
            this.id=id; this.label=label; this.shortcut=shortcut; this.text=text;
        }
    }
    public static final class Replacement {
        public final String text;
        public final int cursor;
        Replacement(String text, int cursor) { this.text=text; this.cursor=cursor; }
    }
    public static void validate(List<Snippet> snippets, boolean immediate) {
        if (snippets.size()>1000) throw new IllegalArgumentException("Maximum 1,000 snippets.");
        Set<String> ids=new HashSet<>(), keys=new HashSet<>();
        for (Snippet s:snippets) {
            if (s.id==null || s.id.isEmpty() || !ids.add(s.id)) throw new IllegalArgumentException("Snippet IDs must be unique.");
            if (s.label==null || s.label.trim().isEmpty() || s.label.length()>200) throw new IllegalArgumentException("Enter a name (maximum 200 characters).");
            if (s.shortcut==null || !s.shortcut.matches("[;:/!.,][!-~]{1,39}") || !keys.add(s.shortcut.toLowerCase(Locale.ROOT)))
                throw new IllegalArgumentException("Use a unique 2–40 character shortcut starting with ; : / ! . or , and no spaces (letter case is ignored).");
            if (s.text==null || s.text.isEmpty() || s.text.length()>8192 || s.text.indexOf('\0')>=0)
                throw new IllegalArgumentException("Snippet text must contain 1–8192 characters.");
        }
        if (immediate) {
            List<String> sorted=new ArrayList<>(keys); Collections.sort(sorted);
            for (int i=1;i<sorted.size();i++) if (sorted.get(i).startsWith(sorted.get(i-1)))
                throw new IllegalArgumentException("Immediate mode cannot use overlapping shortcuts: "+sorted.get(i-1)+" and "+sorted.get(i));
        }
    }
    public static Replacement expand(String before, String after, int cursor, List<Snippet> snippets,
                                      boolean immediate, boolean keepSpace) {
        if (before==null || after==null || after.length()>20000 || cursor<=0 || cursor>after.length()) return null;
        // IMEs may replace a whole composing word. Compare actual content so a
        // normal one-character edit still works; pasted/multi-character edits don't expand.
        if(after.length()!=before.length()+1 ||
            !before.equals(after.substring(0,cursor-1)+after.substring(cursor))) return null;
        int end=cursor;
        char last=after.charAt(cursor-1);
        if (!immediate) {
            if (last!=' ' && last!='\t') return null;
            end--;
        }
        int start=end;
        while(start>0 && !Character.isWhitespace(after.charAt(start-1))) {
            start--; if(end-start>40) return null;
        }
        String token=after.substring(start,end);
        for(Snippet s:snippets) if(s.shortcut.equalsIgnoreCase(token)) {
            String insert=s.text+(!immediate && last==' ' && keepSpace?" ":"");
            return new Replacement(after.substring(0,start)+insert+after.substring(cursor),start+insert.length());
        }
        return null;
    }
    public static boolean secret(String text, boolean strict) {
        String v=text.trim(); if(v.isEmpty()) return false;
        if(Pattern.compile("(?i)(password|passwd|passphrase|secret|api[_ -]?key|access[_ -]?token|authorization)\\s*[:=]").matcher(v).find()) return true;
        if(v.contains("PRIVATE KEY-----") || Pattern.compile("\\beyJ[\\w-]+\\.[\\w-]+\\.[\\w-]+\\b").matcher(v).find()) return true;
        if(v.matches("(?i)(sk-[\\w-]{12,}|gh[pousr]_[\\w]{12,}|AKIA[A-Z0-9]{16})") || v.matches("[0-9]{4,8}")) return true;
        if(v.matches("(?i)https?://.*")) {
            try {
                URI uri=new URI(v);
                if(uri.getUserInfo()!=null) return true;
                String query=uri.getQuery();
                return query!=null && Pattern.compile("(?i)(^|&)([^=&]*(token|password|secret|api.?key|auth|code)[^=&]*)=").matcher(query).find();
            } catch(Exception e) { return true; }
        }
        if(!Pattern.compile("\\s").matcher(v).find()) {
            int groups=0;
            for(String p:new String[]{"[a-z]","[A-Z]","[0-9]","[^\\w]"}) if(Pattern.compile(p).matcher(v).find()) groups++;
            return strict || (v.length()>=8 && groups>=3);
        }
        return false;
    }
    public static String preview(String text) {
        String one=text.replaceAll("\\s+"," ").trim();
        return one.length()>100?one.substring(0,100)+"…":one;
    }
}
