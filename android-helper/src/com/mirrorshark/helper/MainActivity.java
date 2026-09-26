package com.mirrorshark.helper;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;

/** Small status screen: shows whether the helper is ready and lets the owner switch it off. */
public class MainActivity extends Activity {
    private TextView status;
    private Switch toggle;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        int pad = (int) (20 * getResources().getDisplayMetrics().density);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad * 2, pad, pad);
        root.setBackgroundColor(Color.parseColor("#0f1115"));

        TextView title = text("Mirror Shark Helper", 24, "#e8eaf0", true);
        TextView sub = text("Lets Mirror Shark on your computer ask this phone to turn on Wireless debugging. "
                + "You always get a notification and must tap Accept.", 14, "#8b93a5", false);

        toggle = new Switch(this);
        toggle.setText("Accept requests from my computer");
        toggle.setTextColor(Color.parseColor("#e8eaf0"));
        toggle.setChecked(HelperService.isEnabled(this));
        toggle.setOnCheckedChangeListener((v, on) -> {
            HelperService.setEnabled(this, on);
            if (on) HelperService.start(this); else HelperService.stop(this);
            refresh();
        });

        status = text("", 14, "#e8eaf0", false);

        Button dev = new Button(this);
        dev.setText("Open Developer options");
        dev.setOnClickListener(v -> startActivity(new Intent(Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS)));

        LinearLayout.LayoutParams gap = new LinearLayout.LayoutParams(-1, -2);
        gap.topMargin = pad;
        root.addView(title);
        root.addView(sub, gap);
        root.addView(toggle, gap);
        root.addView(status, gap);
        root.addView(dev, gap);
        ScrollView sv = new ScrollView(this);
        sv.addView(root);
        setContentView(sv);

        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 1);
        }
        if (HelperService.isEnabled(this)) HelperService.start(this);
    }

    @Override
    protected void onResume() {
        super.onResume();
        refresh();
    }

    private void refresh() {
        boolean canEnable = checkSelfPermission("android.permission.WRITE_SECURE_SETTINGS") == PackageManager.PERMISSION_GRANTED;
        boolean wifiDebug = Settings.Global.getInt(getContentResolver(), "adb_wifi_enabled", 0) == 1;
        StringBuilder sb = new StringBuilder();
        sb.append(toggle.isChecked() ? "Helper is on and listening.\n" : "Helper is off.\n");
        sb.append("Wireless debugging is ").append(wifiDebug ? "ON.\n" : "OFF.\n");
        sb.append(canEnable
                ? "Ready: after you tap Accept, Wireless debugging is switched on automatically."
                : "Not fully set up: Mirror Shark has not given this app permission yet, so after you tap Accept "
                  + "you will be taken to Developer options to switch it on yourself. In Mirror Shark use "
                  + "More > Set up phone helper while this phone is connected.");
        status.setText(sb.toString());
    }

    private TextView text(String s, int sp, String color, boolean bold) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(sp);
        t.setTextColor(Color.parseColor(color));
        t.setGravity(Gravity.START);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        return t;
    }
}
