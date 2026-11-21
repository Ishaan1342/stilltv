package io.github.ishaan1342.stilltv;

import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.*;
import android.util.AtomicFile;
import java.io.*;
import java.util.List;

/** Only the ADB shell / privileged callers can write. No unauthenticated app-config receiver. */
public final class ConfigProvider extends ContentProvider {
    @Override public boolean onCreate() { return true; }
    private File resolve(Uri uri) throws FileNotFoundException {
        List<String> p = uri.getPathSegments();
        if (p.size() == 1 && p.get(0).equals("pending")) return new File(getContext().getFilesDir(), "config.pending");
        if (p.size() == 2 && p.get(0).equals("photo") && p.get(1).matches("(?:home|dream)-[a-f0-9]{64}\\.jpg")) {
            File dir = new File(getContext().getFilesDir(), "photos");
            if (!dir.exists() && !dir.mkdir()) throw new FileNotFoundException("Photo directory unavailable");
            return new File(dir, p.get(1));
        }
        throw new FileNotFoundException("Unknown resource");
    }
    @Override public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        if (!mode.equals("w")) throw new FileNotFoundException("Write only");
        return ParcelFileDescriptor.open(resolve(uri), ParcelFileDescriptor.MODE_CREATE |
                ParcelFileDescriptor.MODE_TRUNCATE | ParcelFileDescriptor.MODE_WRITE_ONLY);
    }
    @Override public Bundle call(String method, String arg, Bundle extras) {
        // ContentProvider.call does not enforce read/write permissions on all Android versions.
        getContext().enforceCallingOrSelfPermission("android.permission.WRITE_SECURE_SETTINGS", "Privileged configuration only");
        Bundle result = new Bundle();
        if (!"commit".equals(method)) throw new IllegalArgumentException("Unknown operation");
        File pending = new File(getContext().getFilesDir(), "config.pending");
        AtomicFile target = new AtomicFile(new File(getContext().getFilesDir(), "config.json"));
        FileOutputStream output = null;
        try {
            byte[] bytes = Config.read(new FileInputStream(pending), 262144);
            Config config = Config.parse(bytes);
            for (org.json.JSONObject p : config.photos(false)) {
                for (String key : new String[]{"file", "dream"}) {
                    File photo = new File(new File(getContext().getFilesDir(), "photos"), p.getString(key));
                    if (!photo.isFile() || photo.length() > 16 * 1024 * 1024) throw new IOException("Missing or oversized photo");
                    android.graphics.BitmapFactory.Options bounds = new android.graphics.BitmapFactory.Options();
                    bounds.inJustDecodeBounds = true;
                    android.graphics.BitmapFactory.decodeFile(photo.getPath(), bounds);
                    if (bounds.outWidth < 1 || bounds.outWidth > 7680 || bounds.outHeight < 1 || bounds.outHeight > 4320)
                        throw new IOException("Invalid photo dimensions");
                }
            }
            output = target.startWrite(); output.write(bytes); target.finishWrite(output); output = null;
            pending.delete();
            result.putString("result", "ok");
        } catch (Exception error) {
            if (output != null) target.failWrite(output);
            result.putString("error", "Invalid configuration: " + error.getClass().getSimpleName());
        }
        return result;
    }
    @Override public Cursor query(Uri u, String[] p, String s, String[] a, String o) { return null; }
    @Override public String getType(Uri u) { return "application/octet-stream"; }
    @Override public Uri insert(Uri u, ContentValues v) { throw new UnsupportedOperationException(); }
    @Override public int delete(Uri u, String s, String[] a) { throw new UnsupportedOperationException(); }
    @Override public int update(Uri u, ContentValues v, String s, String[] a) { throw new UnsupportedOperationException(); }
}
