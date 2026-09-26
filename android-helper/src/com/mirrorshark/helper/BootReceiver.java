package com.mirrorshark.helper;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Restarts the helper after a reboot or an app update, if the user left it switched on. */
public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (HelperService.isEnabled(context)) {
            try {
                HelperService.start(context);
            } catch (Exception ignored) {
                // the system may refuse a background start; opening the app starts it
            }
        }
    }
}
