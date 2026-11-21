package io.github.ishaan1342.stilltv;

import android.content.Context;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

final class Config {
    static final String APP = "io.github.ishaan1342.stilltv";
    final JSONObject json;
    final String name, theme;
    final int rotation, dream;
    Config(JSONObject value) throws Exception {
        if (value.getInt("schema") != 1) throw new IOException("Unsupported config version");
        name = value.optString("name", "Welcome home");
        theme = value.optString("theme", "cinematic");
        if (name.length() > 48 || !Arrays.asList("cinematic", "quiet", "contrast").contains(theme))
            throw new IOException("Invalid greeting or theme");
        rotation = value.optInt("rotation_seconds", 300);
        dream = value.optInt("dream_seconds", 20);
        if (rotation < 30 || rotation > 3600 || dream < 10 || dream > 300)
            throw new IOException("Invalid slideshow interval");
        JSONArray favorites = value.getJSONArray("favorites");
        if (favorites.length() > 12) throw new IOException("At most twelve favorites");
        for (int i = 0; i < favorites.length(); i++) {
            JSONObject f = favorites.getJSONObject(i);
            if (!f.getString("package").matches("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z][A-Za-z0-9_]*)+")
                    || f.getString("label").length() > 32 || f.getString("label").isEmpty())
                throw new IOException("Invalid favorite");
        }
        JSONArray photos = value.optJSONArray("photos");
        if (photos != null) {
            if (photos.length() > 200) throw new IOException("At most 200 photos");
            for (int i = 0; i < photos.length(); i++) {
                JSONObject p = photos.getJSONObject(i);
                for (String key : Arrays.asList("file", "dream"))
                    if (!p.getString(key).matches("(?:home|dream)-[a-f0-9]{64}\\.jpg"))
                        throw new IOException("Invalid local photo name");
                if (p.optString("caption", "").length() > 80) throw new IOException("Caption too long");
            }
        }
        json = value;
    }
    static byte[] read(InputStream stream, int limit) throws IOException {
        try (InputStream input = stream; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192]; int n;
            while ((n = input.read(buffer)) != -1) {
                if (out.size() + n > limit) throw new IOException("Input too large");
                out.write(buffer, 0, n);
            }
            return out.toByteArray();
        }
    }
    static Config load(Context context) {
        File file = new File(context.getFilesDir(), "config.json");
        try { return parse(read(new FileInputStream(file), 262144)); }
        catch (Exception ignored) {
            try { return parse(read(context.getAssets().open("config.json"), 262144)); }
            catch (Exception error) { throw new IllegalStateException("Invalid bundled config", error); }
        }
    }
    static Config parse(byte[] bytes) throws Exception {
        return new Config(new JSONObject(new String(bytes, StandardCharsets.UTF_8)));
    }
    List<JSONObject> photos(boolean night) {
        List<JSONObject> all = new ArrayList<>(), dark = new ArrayList<>();
        JSONArray array = json.optJSONArray("photos");
        if (array != null) for (int i = 0; i < array.length(); i++) {
            JSONObject p = array.optJSONObject(i);
            if (p != null) { all.add(p); if (p.optBoolean("night", false)) dark.add(p); }
        }
        return night && !dark.isEmpty() ? dark : all;
    }
}
