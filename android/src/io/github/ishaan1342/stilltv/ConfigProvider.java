package io.github.ishaan1342.stilltv;

import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.*;
import android.util.AtomicFile;
import java.io.*;
import java.security.MessageDigest;
import java.util.List;

/** Configuration is writable only by the authorized shell or another privileged caller. */
public final class ConfigProvider extends ContentProvider {
    private static final String TOKEN = "[a-f0-9]{32}";
    private static final String PHOTO = "(?:home|dream)-[a-f0-9]{64}\\.jpg";
    private static final long MAX_PHOTO = 16 * 1024 * 1024;

    @Override public boolean onCreate() { return true; }

    private File staging(String token) throws FileNotFoundException {
        if (token == null || !token.matches(TOKEN)) throw new FileNotFoundException("Invalid upload ID");
        File dir = new File(getContext().getFilesDir(), "staging/" + token);
        if (!dir.isDirectory() && !dir.mkdirs()) throw new FileNotFoundException("Upload directory unavailable");
        return dir;
    }

    private File resolve(Uri uri) throws FileNotFoundException {
        List<String> p = uri.getPathSegments();
        if (p.size() == 2 && p.get(0).equals("pending"))
            return new File(staging(p.get(1)), "config.json");
        if (p.size() == 3 && p.get(0).equals("photo") && p.get(2).matches(PHOTO))
            return new File(staging(p.get(1)), p.get(2));
        throw new FileNotFoundException("Unknown resource");
    }

    @Override public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        if (!mode.equals("w")) throw new FileNotFoundException("Write only");
        return ParcelFileDescriptor.open(resolve(uri), ParcelFileDescriptor.MODE_CREATE |
                ParcelFileDescriptor.MODE_TRUNCATE | ParcelFileDescriptor.MODE_WRITE_ONLY);
    }

    private static void validatePhoto(File photo) throws IOException {
        if (!photo.isFile() || photo.length() == 0 || photo.length() > MAX_PHOTO)
            throw new IOException("Missing or oversized photo");
        android.graphics.BitmapFactory.Options bounds = new android.graphics.BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        android.graphics.BitmapFactory.decodeFile(photo.getPath(), bounds);
        if (bounds.outWidth < 1 || bounds.outWidth > 7680 || bounds.outHeight < 1 || bounds.outHeight > 4320)
            throw new IOException("Invalid photo dimensions");
    }

    private static String checksum(File photo) throws Exception {
        if (photo.length() > MAX_PHOTO) throw new IOException("Oversized photo");
        MessageDigest hash = MessageDigest.getInstance("SHA-256");
        try (InputStream in = new FileInputStream(photo)) {
            byte[] buffer = new byte[65536]; int read;
            while ((read = in.read(buffer)) != -1) hash.update(buffer, 0, read);
        }
        StringBuilder hex = new StringBuilder();
        for (byte b : hash.digest()) hex.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
        return hex.toString();
    }

    private void commitPhoto(String arg) throws Exception {
        String[] parts = arg == null ? new String[0] : arg.split(":", -1);
        if (parts.length != 3 || !parts[1].matches(PHOTO) || !parts[2].matches("[a-f0-9]{64}"))
            throw new IOException("Invalid photo commit");
        File staged = new File(staging(parts[0]), parts[1]);
        validatePhoto(staged);
        if (!checksum(staged).equals(parts[2])) throw new IOException("Incomplete photo upload");
        File dir = new File(getContext().getFilesDir(), "photos");
        if (!dir.isDirectory() && !dir.mkdir()) throw new IOException("Photo directory unavailable");
        File target = new File(dir, parts[1]);
        if (target.exists()) {
            // Active assets are immutable. Never truncate a photo used by the current config.
            if (!checksum(target).equals(parts[2])) throw new IOException("Photo name already has different bytes");
            staged.delete();
        } else {
            try (FileOutputStream sync = new FileOutputStream(staged, true)) { sync.getFD().sync(); }
            if (!staged.renameTo(target)) throw new IOException("Photo publication failed");
        }
    }

    @Override public Bundle call(String method, String arg, Bundle extras) {
        // ContentProvider.call isn't covered by framework permission checks on every Android version.
        getContext().enforceCallingOrSelfPermission("android.permission.WRITE_SECURE_SETTINGS", "Privileged configuration only");
        // Readers and writers share a lock: AtomicFile alone does not coordinate threads.
        synchronized (Config.class) {
        Bundle result = new Bundle();
        AtomicFile target = new AtomicFile(new File(getContext().getFilesDir(), "config.json"));
        FileOutputStream output = null;
        try {
            if ("commit-photo".equals(method)) {
                commitPhoto(arg);
            } else if ("commit".equals(method)) {
                File pending = new File(staging(arg), "config.json");
                byte[] bytes = Config.read(new FileInputStream(pending), 262144);
                Config config = Config.parse(bytes);
                for (org.json.JSONObject p : config.photos(false)) {
                    for (String key : new String[]{"file", "dream"})
                        validatePhoto(new File(new File(getContext().getFilesDir(), "photos"), p.getString(key)));
                }
                output = target.startWrite(); output.write(bytes); output.getFD().sync();
                target.finishWrite(output); output = null;
                byte[] saved = Config.read(target.openRead(), 262144);
                if (!java.util.Arrays.equals(saved, bytes)) throw new IOException("Config readback failed");
                pending.delete(); staging(arg).delete();
            } else {
                throw new IllegalArgumentException("Unknown operation");
            }
            result.putString("result", "ok");
        } catch (Exception error) {
            if (output != null) target.failWrite(output);
            result.putString("error", "Upload rejected: " + error.getClass().getSimpleName());
        }
        return result;
        }
    }

    @Override public Cursor query(Uri u, String[] p, String s, String[] a, String o) { return null; }
    @Override public String getType(Uri u) { return "application/octet-stream"; }
    @Override public Uri insert(Uri u, ContentValues v) { throw new UnsupportedOperationException(); }
    @Override public int delete(Uri u, String s, String[] a) { throw new UnsupportedOperationException(); }
    @Override public int update(Uri u, ContentValues v, String s, String[] a) { throw new UnsupportedOperationException(); }
}
