package com.mirrorshark.helper;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.IBinder;
import android.provider.Settings;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * Listens on the local network for requests from Mirror Shark on the user's computer.
 *
 * Protocol: one JSON object per line over TCP, one request per connection.
 *   {"cmd":"hello"}                     -> {"app":"MirrorSharkHelper","v":1,"name":..,"adb_wifi":0|1,"can_enable":bool}
 *   {"cmd":"enable","pc":"CHARMZ"}      -> asks the user; replies {"status":"enabled|declined|needs_manual|busy|cooldown|timeout|failed"}
 * Nothing is ever changed without the user tapping Accept on this phone.
 */
public class HelperService extends Service {
    static final int PORT = 47620;
    static final String CH_STATUS = "status";
    static final String CH_REQUEST = "requests";
    static final String ACTION_DECIDE = "com.mirrorshark.helper.DECIDE";
    static final long ANSWER_TIMEOUT_MS = 60_000;

    private static final Object LOCK = new Object();
    private static Pending pending;          // at most one request at a time
    private static long cooldownUntil;       // after a decline, ignore new requests for a while
    private static int declineStreak;

    private static class Pending {
        final int id;
        final String pc;
        final String ip;
        final CountDownLatch latch = new CountDownLatch(1);
        volatile boolean accepted;

        Pending(int id, String pc, String ip) { this.id = id; this.pc = pc; this.ip = ip; }
    }

    private ServerSocket server;
    private volatile boolean running;
    private int nextId = 1;

    @Override
    public IBinder onBind(Intent intent) { return null; }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        createChannels();
        startForeground(1, statusNotification());
        if (!running) {
            running = true;
            new Thread(this::acceptLoop, "helper-accept").start();
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        running = false;
        try { if (server != null) server.close(); } catch (Exception ignored) { }
        super.onDestroy();
    }

    // -- decisions from the notification buttons -----------------------------------------------------
    static void decide(int id, boolean accepted) {
        synchronized (LOCK) {
            if (pending != null && pending.id == id) {
                pending.accepted = accepted;
                pending.latch.countDown();
            }
        }
    }

    // -- network ------------------------------------------------------------------------------------------
    private void acceptLoop() {
        try {
            server = new ServerSocket(PORT, 8, null);
            while (running) {
                final Socket s = server.accept();
                new Thread(() -> handle(s), "helper-client").start();
            }
        } catch (Exception e) {
            running = false;
        }
    }

    private void handle(Socket s) {
        try (Socket sock = s) {
            sock.setSoTimeout(5000);
            String line = new BufferedReader(new InputStreamReader(sock.getInputStream(), "UTF-8")).readLine();
            if (line == null || line.length() > 2000) return;
            JSONObject req = new JSONObject(line);
            String cmd = req.optString("cmd");
            JSONObject reply = new JSONObject();
            if ("hello".equals(cmd)) {
                reply.put("app", "MirrorSharkHelper");
                reply.put("v", 1);
                reply.put("name", Build.MANUFACTURER + " " + Build.MODEL);
                reply.put("adb_wifi", wirelessDebuggingOn() ? 1 : 0);
                reply.put("can_enable", canWriteSecureSettings());
            } else if ("enable".equals(cmd)) {
                reply.put("status", handleEnable(req.optString("pc", "A computer"), addressOf(sock)));
            } else {
                return;
            }
            OutputStream out = sock.getOutputStream();
            out.write((reply.toString() + "\n").getBytes("UTF-8"));
            out.flush();
        } catch (Exception ignored) {
        }
    }

    private static String addressOf(Socket s) {
        InetAddress a = s.getInetAddress();
        return a == null ? "?" : a.getHostAddress();
    }

    private String handleEnable(String pc, String ip) throws InterruptedException {
        pc = pc.length() > 40 ? pc.substring(0, 40) : pc;
        Pending mine;
        synchronized (LOCK) {
            if (System.currentTimeMillis() < cooldownUntil) return "cooldown";
            if (pending != null) return "busy";
            mine = new Pending(nextId++, pc, ip);
            pending = mine;
        }
        showRequestNotification(mine);
        boolean answered = mine.latch.await(ANSWER_TIMEOUT_MS, TimeUnit.MILLISECONDS);
        synchronized (LOCK) { pending = null; }
        cancelRequestNotification();
        if (!answered) return "timeout";
        if (!mine.accepted) {
            // repeated declines -> back off, so a noisy device on the network cannot keep prompting
            declineStreak++;
            cooldownUntil = System.currentTimeMillis() + (declineStreak >= 3 ? 300_000 : 30_000);
            return "declined";
        }
        declineStreak = 0;
        return enableWirelessDebugging();
    }

    // -- the setting -------------------------------------------------------------------------------------
    private boolean wirelessDebuggingOn() {
        return Settings.Global.getInt(getContentResolver(), "adb_wifi_enabled", 0) == 1;
    }

    private boolean canWriteSecureSettings() {
        return checkSelfPermission("android.permission.WRITE_SECURE_SETTINGS") == PackageManager.PERMISSION_GRANTED;
    }

    private String enableWirelessDebugging() {
        if (!canWriteSecureSettings()) {
            showManualNotification();
            return "needs_manual";
        }
        try {
            ContentResolver cr = getContentResolver();
            if (Settings.Global.getInt(cr, "development_settings_enabled", 0) == 0) {
                Settings.Global.putInt(cr, "development_settings_enabled", 1);
            }
            Settings.Global.putInt(cr, "adb_wifi_enabled", 1);
            return wirelessDebuggingOn() ? "enabled" : "failed";
        } catch (SecurityException e) {
            showManualNotification();
            return "needs_manual";
        }
    }

    // -- notifications ---------------------------------------------------------------------------------------
    private void createChannels() {
        NotificationManager nm = getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel(CH_STATUS, "Helper running", NotificationManager.IMPORTANCE_MIN));
        NotificationChannel req = new NotificationChannel(CH_REQUEST, "Requests from your computer", NotificationManager.IMPORTANCE_HIGH);
        req.setDescription("Asks before turning on Wireless debugging");
        nm.createNotificationChannel(req);
    }

    private Notification statusNotification() {
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        return new Notification.Builder(this, CH_STATUS)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle("Mirror Shark Helper is on")
                .setContentText("Ready to receive a request from your computer")
                .setContentIntent(open)
                .setOngoing(true)
                .build();
    }

    private PendingIntent decisionIntent(int id, boolean accept) {
        Intent i = new Intent(this, ActionReceiver.class).setAction(ACTION_DECIDE)
                .putExtra("id", id).putExtra("accept", accept);
        return PendingIntent.getBroadcast(this, id * 2 + (accept ? 1 : 0), i,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    private void showRequestNotification(Pending p) {
        Notification.Action accept = new Notification.Action.Builder(null, "Accept", decisionIntent(p.id, true)).build();
        Notification.Action decline = new Notification.Action.Builder(null, "Decline", decisionIntent(p.id, false)).build();
        Notification n = new Notification.Builder(this, CH_REQUEST)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle(p.pc + " wants to turn on Wireless debugging")
                .setContentText("Request from " + p.ip + ". Accept only if this is your own computer.")
                .setStyle(new Notification.BigTextStyle().bigText("Request from " + p.ip + " (" + p.pc
                        + "). Wireless debugging lets that computer mirror and control this phone. "
                        + "Accept only if it is your own computer."))
                .setCategory(Notification.CATEGORY_MESSAGE)
                .setPriority(Notification.PRIORITY_HIGH)
                .setTimeoutAfter(ANSWER_TIMEOUT_MS)
                .addAction(accept)
                .addAction(decline)
                .setAutoCancel(true)
                .build();
        getSystemService(NotificationManager.class).notify(2, n);
    }

    private void cancelRequestNotification() {
        getSystemService(NotificationManager.class).cancel(2);
    }

    private void showManualNotification() {
        Intent i = new Intent(Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        PendingIntent open = PendingIntent.getActivity(this, 5, i, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification n = new Notification.Builder(this, CH_REQUEST)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle("Turn on Wireless debugging")
                .setContentText("Tap to open Developer options, then switch Wireless debugging on.")
                .setContentIntent(open)
                .setAutoCancel(true)
                .build();
        getSystemService(NotificationManager.class).notify(3, n);
    }

    // -- helpers for the other components -----------------------------------------------------------------------
    static boolean isEnabled(Context c) {
        SharedPreferences p = c.getSharedPreferences("helper", MODE_PRIVATE);
        return p.getBoolean("enabled", true);
    }

    static void setEnabled(Context c, boolean on) {
        c.getSharedPreferences("helper", MODE_PRIVATE).edit().putBoolean("enabled", on).apply();
    }

    static void start(Context c) {
        c.startForegroundService(new Intent(c, HelperService.class));
    }

    static void stop(Context c) {
        c.stopService(new Intent(c, HelperService.class));
    }
}
