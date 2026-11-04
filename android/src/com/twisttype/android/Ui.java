package com.twisttype.android;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.*;
import android.view.*;
import android.widget.*;

public final class Ui {
    public static final int PURPLE=0xff37318c,LAVENDER=0xffe9e9fc,BG=0xfffafafe,INK=0xff262633,
        MUTED=0xff565b6d,WHITE=Color.WHITE,NAVY=0xff14233b,BLUE=0xff0066ff;
    public static int dp(Context c,int v) { return (int)(v*c.getResources().getDisplayMetrics().density+.5f); }
    public static GradientDrawable round(int color,int radius) { GradientDrawable g=new GradientDrawable();g.setColor(color);g.setCornerRadius(radius*2f);return g; }
    public static StateListDrawable selector(int normal,int pressed) {
        StateListDrawable d=new StateListDrawable();d.addState(new int[]{android.R.attr.state_pressed},round(pressed,8));d.addState(new int[]{},round(normal,8));return d;
    }
    public static LinearLayout column(Context c) { LinearLayout l=new LinearLayout(c);l.setOrientation(LinearLayout.VERTICAL);return l; }
    public static LinearLayout row(Context c) { LinearLayout l=new LinearLayout(c);l.setOrientation(LinearLayout.HORIZONTAL);l.setGravity(Gravity.CENTER_VERTICAL);return l; }
    public static TextView text(Context c,String value,int size,int color) {
        TextView t=new TextView(c);t.setText(value);t.setTextSize(size);t.setTextColor(color);t.setPadding(0,dp(c,5),0,dp(c,5));return t;
    }
    public static Button button(Context c,String title,View.OnClickListener action,boolean primary) {
        Button b=new Button(c);b.setText(title);b.setAllCaps(false);b.setTextColor(primary?WHITE:PURPLE);b.setTextSize(14);
        b.setBackground(selector(primary?PURPLE:LAVENDER,primary?0xff292467:0xffd8d6f5));
        b.setPadding(dp(c,13),dp(c,8),dp(c,13),dp(c,8));b.setMinHeight(dp(c,44));
        b.setOnClickListener(action);return b;
    }
    public static LinearLayout card(Context c,int color) {
        LinearLayout l=column(c); int p=dp(c,16);l.setPadding(p,p,p,p);l.setBackground(round(color,10));
        return l;
    }
    public static void gap(LinearLayout l,int amount) { Space v=new Space(l.getContext());l.addView(v,new LinearLayout.LayoutParams(1,dp(l.getContext(),amount))); }
    public static void toast(Context c,String s) { Toast.makeText(c,s,Toast.LENGTH_LONG).show(); }
}
