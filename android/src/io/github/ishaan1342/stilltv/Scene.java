package io.github.ishaan1342.stilltv;

import android.content.Context;
import android.graphics.*;
import android.graphics.drawable.Drawable;
import android.os.Handler;
import android.widget.ImageView;
import org.json.JSONObject;
import java.io.File;
import java.util.*;
import java.util.concurrent.*;

final class Scene {
    private final Context context;
    private final ImageView image;
    private final Handler main = new Handler(android.os.Looper.getMainLooper());
    private final ExecutorService decode = Executors.newSingleThreadExecutor();
    private int generation = 0, index = 0;
    private boolean closed = false;
    Scene(Context c, ImageView view) { context = c; image = view; image.setImageDrawable(new Landscape()); }
    String next(Config config, boolean dream) {
        int hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY);
        List<JSONObject> photos = config.photos(hour >= 21 || hour < 7);
        if (photos.isEmpty()) return "A little more space to unwind.";
        JSONObject photo = photos.get(index++ % photos.size());
        File file = new File(new File(context.getFilesDir(), "photos"), photo.optString(dream ? "dream" : "file"));
        int request = ++generation;
        decode.execute(() -> {
            BitmapFactory.Options options = new BitmapFactory.Options();
            options.inJustDecodeBounds = true; BitmapFactory.decodeFile(file.getPath(), options);
            int target = Math.min(1920, Math.max(image.getWidth(), image.getHeight()));
            target = Math.max(target, 960);
            options.inSampleSize = 1;
            while (Math.max(options.outWidth, options.outHeight) / (options.inSampleSize * 2) >= target) options.inSampleSize *= 2;
            options.inJustDecodeBounds = false; options.inPreferredConfig = Bitmap.Config.RGB_565;
            Bitmap bitmap = BitmapFactory.decodeFile(file.getPath(), options);
            main.post(() -> {
                if (!closed && request == generation && bitmap != null) image.setImageBitmap(bitmap);
                else if (bitmap != null) bitmap.recycle();
            });
        });
        return photo.optString("caption", "");
    }
    void close() { closed = true; generation++; decode.shutdownNow(); main.removeCallbacksAndMessages(null); }
    static final class Landscape extends Drawable {
        final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        @Override public void draw(Canvas canvas) {
            Rect b = getBounds(); float w = b.width(), h = b.height();
            paint.setShader(new LinearGradient(0, 0, 0, h, new int[]{0xff99b7ae,0xff3c6763,0xff142e32}, null, Shader.TileMode.CLAMP));
            canvas.drawRect(b, paint); paint.setShader(null);
            int[] colors = {0xff608582,0xff3b6967,0xff214e50,0xff173b3f};
            for (int layer = 0; layer < 4; layer++) {
                Path p = new Path(); p.moveTo(0, h);
                for (int n = 0; n <= 16; n++) {
                    float x = w * n / 16f;
                    float y = h * (.42f + layer * .105f) + (float)Math.sin(n * .6 + layer * 1.8) * h * .065f;
                    p.lineTo(x, y);
                }
                p.lineTo(w,h); p.close(); paint.setColor(colors[layer]); canvas.drawPath(p,paint);
            }
        }
        @Override public void setAlpha(int a) { }
        @Override public void setColorFilter(ColorFilter f) { }
        @Override public int getOpacity() { return PixelFormat.OPAQUE; }
    }
}
