package com.twisttype.android;
import android.app.Activity;
import android.os.Bundle;
import android.text.InputType;
import android.widget.*;
public final class TestActivity extends Activity {
    @Override public void onCreate(Bundle b) {
        super.onCreate(b);LinearLayout root=Ui.column(this);int p=Ui.dp(this,20);root.setPadding(p,p,p,p);root.setBackgroundColor(Ui.BG);
        root.addView(Ui.text(this,"Try your snippets",25,Ui.INK));
        root.addView(Ui.text(this,"With TwistType's Accessibility service enabled, type ;thanks and then Space using your usual keyboard. Autocorrect may interfere with some shortcuts; punctuation prefixes help.",15,Ui.MUTED));
        EditText edit=new EditText(this);edit.setId(R.id.test_field);edit.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_MULTI_LINE|InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        edit.setHint("Type here…");edit.setMinLines(8);root.addView(edit,new LinearLayout.LayoutParams(-1,0,1));
        root.addView(Ui.button(this,"Back to TwistType",v->finish(),false));setContentView(root);
    }
}
