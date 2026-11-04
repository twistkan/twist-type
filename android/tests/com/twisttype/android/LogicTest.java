package com.twisttype.android;
import java.util.*;
public final class LogicTest {
    private static int checks=0;
    static void check(boolean value,String message){checks++;if(!value)throw new AssertionError(message);}
    static boolean rejects(List<Logic.Snippet> list,boolean immediate){try{Logic.validate(list,immediate);return false;}catch(IllegalArgumentException e){return true;}}
    public static void main(String[] args){
        List<Logic.Snippet> list=Arrays.asList(new Logic.Snippet("1","Hi",";hi","Hello \u03a9 \ud83d\ude00"),new Logic.Snippet("2","Signoff",";sig","Kind regards,\nYour name"));
        Logic.validate(list,false);check(true,"valid library");
        Logic.Replacement r=Logic.expand(";hi",";hi ",4,list,false,true);
        check(r!=null && r.text.equals("Hello \u03a9 \ud83d\ude00 ") && r.cursor==r.text.length(),"Space expansion, Unicode, cursor");
        r=Logic.expand(";hi",";hi\t",4,list,false,true);check(r!=null && r.text.equals("Hello \u03a9 \ud83d\ude00"),"Tab consumed");
        r=Logic.expand(";h",";hi",3,list,true,true);check(r!=null && r.text.equals("Hello \u03a9 \ud83d\ude00"),"Immediate");
        check(Logic.expand("",";hi ",4,list,false,true)==null,"Pasted text must not expand");
        check(Logic.expand("hello;hi","hello;hi ",9,list,false,true)==null,"Whole-token matching");
        r=Logic.expand(";HI",";HI ",4,list,false,true);check(r!=null && r.text.equals("Hello \u03a9 \ud83d\ude00 "),"Uppercase Space trigger preserves saved text");
        r=Logic.expand(";Hi",";Hi\t",4,list,false,true);check(r!=null && r.text.equals("Hello \u03a9 \ud83d\ude00"),"Mixed-case Tab");
        r=Logic.expand(";H",";Hi",3,list,true,true);check(r!=null && r.text.equals("Hello \u03a9 \ud83d\ude00"),"Mixed-case immediate");
        List<Logic.Snippet> upper=Arrays.asList(new Logic.Snippet("u","Upper",";SIG","Saved Case"));
        r=Logic.expand(";sig",";sig ",5,upper,false,false);check(r!=null && r.text.equals("Saved Case"),"Uppercase saved shortcut");
        check(Logic.expand(";hi",";hi",3,list,false,true)==null,"Unchanged event");
        r=Logic.expand("Before ;hi after","Before ;hi  after",11,list,false,true);
        check(r!=null && r.text.equals("Before Hello \u03a9 \ud83d\ude00  after"),"Preserve following text");
        r=Logic.expand(";sig",";sig ",5,list,false,false);check(r!=null && r.text.equals("Kind regards,\nYour name"),"Multiline and Space option");
        String[] bad={"password: synthetic only","P@ssword123","hunter2","123456","api_key=abc","https://u:p@example.com","https://example.com/?token=abc","-----BEGIN PRIVATE KEY-----"};
        for(String s:bad)check(Logic.secret(s,true),"Sensitive value must be omitted");
        check(!Logic.secret("An ordinary copied phrase.",true),"Ordinary phrase");
        check(!Logic.secret("https://example.com/docs",true),"Plain URL");
        check(Logic.secret("https://example.com/?%74oken=synthetic",true),"Encoded credential parameter");
        check(!Logic.secret("hello",false),"Relaxed single-word option");
        check(Logic.secret("Ab3$randomsecret",false),"Strong secret patterns stay filtered");
        check(Logic.preview("one\n two  three").equals("one two three"),"Single-line preview");
        check(rejects(Arrays.asList(list.get(0),new Logic.Snippet("3","Other",";higher","x")),true),"Prefix collision");
        check(rejects(Arrays.asList(list.get(0),new Logic.Snippet("3","Other",";hi","x")),false),"Duplicate shortcut");
        check(rejects(Arrays.asList(new Logic.Snippet("1","Name","word","x")),false),"Shortcut prefix validation");
        check(rejects(Arrays.asList(list.get(0),new Logic.Snippet("3","Other",";HI","x")),false),"Case-only duplicate");
        check(rejects(Arrays.asList(list.get(0),new Logic.Snippet("3","Other",";HIGHER","x")),true),"Mixed-case prefix collision");
        Locale original=Locale.getDefault();try{Locale.setDefault(new Locale("tr","TR"));
            check(rejects(Arrays.asList(list.get(0),new Logic.Snippet("3","Other",";HI","x")),false),"Locale-independent normalization");
        }finally{Locale.setDefault(original);}
        System.out.println("PASS: "+checks+" Android core checks");
    }
}
