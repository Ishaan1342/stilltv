package io.github.ishaan1342.stilltv;

import android.app.*;
import android.content.*;
import android.content.pm.*;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.media.tv.*;
import android.net.Uri;
import android.os.*;
import android.provider.Settings;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.text.SimpleDateFormat;
import java.util.*;

/** Native, remote-first home. No accessibility hooks, background service or network permission. */
public final class MainActivity extends Activity {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private Config config;
    private Scene scene;
    private TextView clock, date, greeting, caption;
    private boolean foreground;
    private final Runnable tick = new Runnable() {
        @Override public void run() {
            if (!foreground) return;
            Date now = new Date();
            clock.setText(new SimpleDateFormat("HH:mm", Locale.getDefault()).format(now));
            date.setText(new SimpleDateFormat("EEEE, d MMMM", Locale.getDefault()).format(now).toUpperCase(Locale.getDefault()));
            int hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY);
            greeting.setText(hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening");
            handler.postDelayed(this, 60000 - System.currentTimeMillis() % 60000);
        }
    };
    private final Runnable rotate = new Runnable() {
        @Override public void run() {
            if (!foreground) return;
            caption.setText(scene.next(config, false));
            handler.postDelayed(this, config.rotation * 1000L);
        }
    };
    private int dp(float n) { return Math.round(n * getResources().getDisplayMetrics().density); }
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY);
    }
    @Override public void onResume() {
        super.onResume(); foreground = true; config = Config.load(this); build(); tick.run(); rotate.run();
    }
    @Override public void onPause() {
        foreground = false; handler.removeCallbacksAndMessages(null); if (scene != null) scene.close(); super.onPause();
    }
    private TextView text(String label, float size, String family) {
        TextView view = new TextView(this); view.setText(label); view.setTextColor(Color.WHITE); view.setTextSize(size);
        view.setTypeface(Typeface.create(family, Typeface.NORMAL)); view.setIncludeFontPadding(false); return view;
    }
    private LinearLayout column() { LinearLayout v = new LinearLayout(this); v.setOrientation(LinearLayout.VERTICAL); return v; }
    private FrameLayout.LayoutParams position(int w, int h, int gravity, int left, int top, int right, int bottom) {
        FrameLayout.LayoutParams p = new FrameLayout.LayoutParams(w < 0 ? w : dp(w), h < 0 ? h : dp(h), gravity);
        p.setMargins(dp(left),dp(top),dp(right),dp(bottom)); return p;
    }
    private Button button(String label, Runnable action) {
        Button view = new Button(this); view.setText(label); view.setTextSize(16); view.setTextColor(0xffe8f0e9);
        view.setAllCaps(false); view.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        view.setPadding(dp(15),dp(9),dp(15),dp(9)); view.setMinWidth(0); view.setMinimumWidth(0);
        view.setContentDescription(label); view.setOnClickListener(v -> action.run());
        view.setOnFocusChangeListener((v,focused) -> {
            GradientDrawable background = new GradientDrawable(); background.setCornerRadius(dp(8));
            background.setColor(focused ? 0x44ffffff : 0x00000000);
            background.setStroke(dp(1),focused ? 0xffd5efc7 : 0x00000000); v.setBackground(background);
            ((Button)v).setTextColor(focused ? Color.WHITE : 0xffd1dbd2);
        });
        view.setBackgroundColor(Color.TRANSPARENT); return view;
    }
    private void build() {
        if (scene != null) scene.close();
        FrameLayout root = new FrameLayout(this); root.setBackgroundColor(0xff132c2c);
        ImageView background = new ImageView(this); background.setScaleType(ImageView.ScaleType.CENTER_CROP);
        root.addView(background, new FrameLayout.LayoutParams(-1,-1)); scene = new Scene(this,background);
        View shade = new View(this);
        shade.setBackground(new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
                new int[]{0x66000000,0x00000000,0x00000000,0x99000000}));
        root.addView(shade,new FrameLayout.LayoutParams(-1,-1));
        if (config.theme.equals("contrast")) { View scrim = new View(this); scrim.setBackgroundColor(0x66000000); root.addView(scrim,new FrameLayout.LayoutParams(-1,-1)); }
        LinearLayout time = column(); clock = text("",72,"sans-serif-thin"); date = text("",11,"sans-serif-medium");
        date.setLetterSpacing(.15f); time.addView(clock); time.addView(date);
        root.addView(time,position(-2,-2,Gravity.TOP|Gravity.START,48,38,0,0));
        LinearLayout tools = new LinearLayout(this); tools.setGravity(Gravity.CENTER);
        tools.addView(button("Inputs",this::inputs)); tools.addView(button("Apps",this::library));
        tools.addView(button("Settings",() -> { try { startActivity(new Intent(Settings.ACTION_SETTINGS)); } catch (Exception e) { toast("TV settings are unavailable."); } }));
        root.addView(tools,position(-2,-2,Gravity.TOP|Gravity.END,0,44,40,0));
        LinearLayout welcome = column(); greeting = text("",13,"sans-serif");
        TextView name = text(config.name,34,"serif"); name.setTypeface(Typeface.create("serif",Typeface.ITALIC));
        name.setMaxWidth(dp(400)); name.setMaxLines(2);
        caption = text("",11,"sans-serif"); caption.setTextColor(0xffc5d0c8); caption.setMaxWidth(dp(380));
        welcome.addView(greeting); if (!config.theme.equals("quiet")) welcome.addView(name); welcome.addView(caption);
        root.addView(welcome,position(-2,-2,Gravity.BOTTOM|Gravity.START,48,0,0,48));
        HorizontalScrollView scroll = new HorizontalScrollView(this); scroll.setHorizontalScrollBarEnabled(false);
        LinearLayout favorites = new LinearLayout(this); favorites.setGravity(Gravity.CENTER_VERTICAL);
        JSONArray array = config.json.optJSONArray("favorites"); Button first = null;
        if (array != null) for (int i = 0; i < array.length(); i++) {
            JSONObject favorite = array.optJSONObject(i); if (favorite == null) continue;
            String pkg = favorite.optString("package"), label = favorite.optString("label");
            if (getPackageManager().getLeanbackLaunchIntentForPackage(pkg) == null) continue;
            Button b = button(label,() -> launch(pkg)); favorites.addView(b); if (first == null) first = b;
        }
        if (first == null) { first = button("Browse apps",this::library); favorites.addView(first); }
        scroll.addView(favorites); FrameLayout.LayoutParams dock = position(-2,64,Gravity.BOTTOM|Gravity.END,0,0,40,42);
        // Half-screen dock keeps long favorites from colliding with the greeting at any logical resolution.
        dock.width = Math.max(dp(260),getResources().getDisplayMetrics().widthPixels / 2);
        root.addView(scroll,dock); setContentView(root); first.requestFocus();
    }
    private void toast(String message) { Toast.makeText(this,message,Toast.LENGTH_LONG).show(); }
    private void launch(String pkg) {
        Intent intent = getPackageManager().getLeanbackLaunchIntentForPackage(pkg);
        if (intent == null) { toast("This TV app is not available."); return; }
        try { startActivity(intent); } catch (Exception e) { toast("The TV refused to open this app."); }
    }
    private void library() {
        PackageManager pm = getPackageManager();
        List<ResolveInfo> apps = pm.queryIntentActivities(new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LEANBACK_LAUNCHER),0);
        apps.sort((a,b) -> a.loadLabel(pm).toString().compareToIgnoreCase(b.loadLabel(pm).toString()));
        List<String> labels = new ArrayList<>(), packages = new ArrayList<>();
        for (ResolveInfo app : apps) if (!app.activityInfo.packageName.equals(getPackageName()) && !packages.contains(app.activityInfo.packageName)) {
            labels.add(app.loadLabel(pm).toString()); packages.add(app.activityInfo.packageName);
        }
        new AlertDialog.Builder(this).setTitle("Your apps").setItems(labels.toArray(new String[0]),(d,n) -> launch(packages.get(n))).setNegativeButton("Close",null).show();
    }
    private void inputs() {
        TvInputManager manager = (TvInputManager)getSystemService(TV_INPUT_SERVICE);
        List<TvInputInfo> sources = new ArrayList<>(); List<String> labels = new ArrayList<>();
        if (manager != null) for (TvInputInfo input : manager.getTvInputList()) {
            if (input.getType() != TvInputInfo.TYPE_HDMI) continue;
            CharSequence custom = input.loadCustomLabel(this);
            String label = String.valueOf(custom == null || custom.length() == 0 ? input.loadLabel(this) : custom);
            int state = manager.getInputState(input.getId());
            labels.add(label + (state == TvInputManager.INPUT_STATE_CONNECTED ? " · connected" : state == TvInputManager.INPUT_STATE_CONNECTED_STANDBY ? " · standby" : " · no signal"));
            sources.add(input);
        }
        if (sources.isEmpty()) { toast("No HDMI inputs are exposed. Use your TV remote’s Input button."); return; }
        new AlertDialog.Builder(this).setTitle("HDMI inputs").setItems(labels.toArray(new String[0]),(d,n) -> openInput(sources.get(n))).setNegativeButton("Close",null).show();
    }
    private void openInput(TvInputInfo source) {
        // One attempt, never a retry loop. Source IDs are discovered, never inferred from a row number.
        Intent intent = new Intent(Intent.ACTION_VIEW, TvContract.buildChannelUriForPassthroughInput(source.getId()));
        if (android.os.Build.MANUFACTURER.equalsIgnoreCase("Sony")) intent.setPackage("com.sony.dtv.tvx");
        try { startActivity(intent); }
        catch (Exception error) { toast("The TV refused this input. Complete TV setup or use the remote’s Input button."); }
    }
    @Override public void onBackPressed() { /* Home is the root; never exit to a blank screen. */ }
}
