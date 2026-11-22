# StillTV

A simple home screen for Android TV: your photos, your apps, and an input picker.
No recommendations feed or account to sign into.

![Layout sketch, not a screenshot from a TV](docs/preview.svg)

StillTV has two parts: a small native Android app and a Python tool for setting it up over ADB.
The app works offline. The tool can install it, prepare photos, change the default Home app,
and undo that change. Package cleanup is optional and separate.

**Early version:** the launcher and screensaver have run on one Sony TV. Default Home replacement
didn't work on that TV; the tool restored the previous settings. Keep a working launcher available.
The [test record](docs/verification.md) says what has and hasn't been checked.

## What it does

- Shows a clock, a greeting, app shortcuts and local photos.
- Opens a list of installed TV apps and the HDMI inputs Android exposes.
- Includes a photo screensaver with a clock that moves between corners.
- Prepares 4K photos locally. Keep the whole image in a frame, or fill the screen with landscapes.
- Saves the old Home setting before changing it. The stock launcher stays installed and enabled.
- Can disable individually reviewed packages using a saved plan, with a journal for recovery.
  The included Sony profile disables nothing until you add reviewed candidates.

The Android app requests no permissions, including network access. It has no analytics or
third-party runtime libraries. Apps you launch from it still use their own connections.

## Try it

You'll need Python 3.11+, `adb`, an Android/Google TV running Android 8.0 (API 26) or later,
and the TV remote. Other TV operating systems aren't supported; Fire TV Home replacement isn't either.

```bash
git clone https://github.com/Ishaan1342/stilltv.git
cd stilltv
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install '.[photos]'

# Enable debugging on the TV and approve this computer on its screen.
adb connect <tv-host>:5555
stilltv --device <adb-serial> inspect
```

`inspect` only reads the TV. Its output includes device and app details, so keep it private.
You choose the device explicitly; StillTV doesn't scan your network.

Build the APK using the [build instructions](docs/build.md), then install it:

```bash
python tools/build_android.py
stilltv --device <adb-serial> install --apk build/android/stilltv.apk
stilltv --device <adb-serial> open
```

Installing doesn't change Home or your screensaver. `open` brings StillTV to the front, so run
it when you're not watching or playing something. Missing favorite apps are simply left out.
When updating StillTV, update the CLI and rebuild/install the APK together; they share the photo
upload format.

## Photos and shortcuts

Keep your photos, config and generated files outside Git checkouts. The CLI checks output paths
for this. It leaves the original photos alone and removes metadata from the prepared copies.

```bash
# 3840 × 2160 by default. Keeps the whole photo visible against a blurred background.
stilltv photos --source /path/to/originals --out /path/to/prepared

# For landscapes: fill the screen instead. Edges may be cropped to 16:9.
stilltv photos --source /path/to/landscapes --out /path/to/prepared-landscapes --layout fill
```

Copy `android/assets/config.json` somewhere private. Edit the name, theme and app shortcuts,
then copy the `photos` array from the generated `photos.json` into it.

```bash
stilltv --device <adb-serial> configure --config /private/home.json --photos /path/to/prepared
stilltv --device <adb-serial> open
```

Themes are `cinematic`, `quiet` (no name), and `contrast` (darker background). Captions are optional.
Darker photos are preferred at night. The photo tool doesn't detect faces; use the default framed
layout for photos you don't want cropped. A 4K file doesn't guarantee a 4K Android UI surface:
that depends on the TV's firmware.

## Make it Home

Try the app first. When you're ready:

```bash
stilltv --device <adb-serial> activate --confirm-home-change
# Add --pause-projectivy only if its accessibility override intercepts Home.

# To go back, use the journal path printed by activate:
stilltv --device <adb-serial> restore-home --journal /private/state/device/home-run.json
```

Check the actual remote's Home and Input buttons afterwards. The CLI sends a Home key event,
but that can't prove every hardware button works. Choose **StillTV Photos** in Android's
Screen saver settings if you want the screensaver too.

## Optional package cleanup

You don't need to disable system packages to use the launcher. If you do want to, read
[how plans and recovery work](docs/architecture.md) first. Check each package on your exact TV;
`profiles/example.json` is a test example, not a cleanup list.

```bash
stilltv --device <adb-serial> plan --profile profiles/sony-android12.json --out /private/plan.json
# Read the plan, then pass its full approval hash:
stilltv --device <adb-serial> apply --plan /private/plan.json --approve <full-plan-sha256>
stilltv --device <adb-serial> restore --journal /private/state/device/plan/journal.json
```

Plans belong to one TV and one observed state. The tool refuses stale plans and protects Android,
Google, input, setup, update, accessibility and other essential components. There is no force flag.
Recovery uses a journal, not a firmware backup. A disconnected or powered-off TV may need manual
recovery once ADB is available again. State lives in `$XDG_STATE_HOME/stilltv` or `~/.local/state/stilltv`.

Once you've checked Home, HDMI and recovery, [turn off debugging](docs/security.md).

## Development

```bash
python -m pip install '.[photos,dev]'
python -m unittest discover -s tests -v
ruff check src tests tools
ruff format --check src tests tools
python -m build
```

CI runs Python tests on Linux, macOS and Windows, checks an installed wheel, and builds the
Android APK on Linux. It doesn't run the app on a TV. See [contributing](CONTRIBUTING.md),
[architecture](docs/architecture.md) and [security](SECURITY.md).

## Where this started

Inspired by [Take Back Your TV](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/advanced_llm_apps/take-back-your-tv)
and [CleanYourTV](https://github.com/Gathin23/cleanyourtv). StillTV is a separate implementation,
with a CLI and tests for changes and recovery. CleanYourTV has more device-specific experience;
we haven't benchmarked StillTV against it. [More on the differences](docs/comparison.md).

MIT licensed.
