package io.github.ishaan1342.stilltv;

import android.service.dreams.DreamService;
import android.os.*;
import android.graphics.Color;
import android.view.Gravity;
import android.widget.*;
import java.text.SimpleDateFormat;
import java.util.*;

/** Local prepared photos; clock drifts between corners to reduce static-panel exposure. */
public final class PhotoDream extends DreamService {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private Scene scene;
    private Config config;
    private TextView clock;
    private boolean active;
    private int corner;
    private final Runnable step = new Runnable() {
        @Override public void run() {
            if (!active) return;
            scene.next(config,true);
            clock.setText(new SimpleDateFormat("HH:mm",Locale.getDefault()).format(new Date()));
            FrameLayout.LayoutParams p = (FrameLayout.LayoutParams)clock.getLayoutParams();
            int[] corners = {Gravity.TOP|Gravity.START,Gravity.TOP|Gravity.END,Gravity.BOTTOM|Gravity.END,Gravity.BOTTOM|Gravity.START};
            p.gravity = corners[corner++ % 4]; clock.setLayoutParams(p);
            handler.postDelayed(this,config.dream * 1000L);
        }
    };
    @Override public void onAttachedToWindow() {
        super.onAttachedToWindow(); setInteractive(false); setFullscreen(true); setScreenBright(false);
        config = Config.load(this); FrameLayout root = new FrameLayout(this);
        ImageView image = new ImageView(this); image.setScaleType(ImageView.ScaleType.CENTER_CROP);
        root.addView(image,new FrameLayout.LayoutParams(-1,-1)); scene = new Scene(this,image);
        clock = new TextView(this); clock.setTextColor(Color.WHITE); clock.setTextSize(28); clock.setAlpha(.6f);
        FrameLayout.LayoutParams p = new FrameLayout.LayoutParams(-2,-2); int margin = Math.round(24*getResources().getDisplayMetrics().density);
        p.setMargins(margin,margin,margin,margin); root.addView(clock,p); setContentView(root); active = true; step.run();
    }
    @Override public void onDetachedFromWindow() {
        active = false; handler.removeCallbacksAndMessages(null); if (scene != null) scene.close(); super.onDetachedFromWindow();
    }
}
