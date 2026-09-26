package com.mirrorshark.helper;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Handles the Accept / Decline buttons of the request notification. */
public class ActionReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (HelperService.ACTION_DECIDE.equals(intent.getAction())) {
            HelperService.decide(intent.getIntExtra("id", -1), intent.getBooleanExtra("accept", false));
        }
    }
}
