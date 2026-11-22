# What has been tested

Last checked: 22 November 2026.

## Local checks

- 65 Python tests pass on Python 3.13 / ARM64 Linux. These include wrong-device and stale-plan
  refusal, interrupted uploads, lost acknowledgements, disk-full rollback and repeated Home recovery.
- Ruff lint and formatting pass.
- The Android APK builds and its signature verifies using platform/build-tools 34, JDK 17 and
  native ARM64 aapt2/zipalign. It requests no Android permissions.
- Host-JDK checks cover photo decode sizing, including 4K and smaller memory budgets.
- A rebuild with invalid stale class, DEX and generated-source files in the output directory passes
  without including those files.
- Source and wheel builds pass. The Java checks are included in the source archive. The wheel's CLI
  also passes a smoke check in a fresh environment outside the checkout.
- Read-only inventory and a zero-change package plan have worked on the development Sony TV.

GitHub checks are recorded against each commit in
[Actions](https://github.com/Ishaan1342/stilltv/actions/workflows/ci.yml). A local pass isn't a CI result.

## Source review

GPT-6 Astra at high reasoning reviewed the source, tests, build scripts, CI, profiles and docs.
This was the available Astra model, not Astra 6.2. No unresolved release-blocking findings remained
at the end of that source review.

The review led to fixes for interrupted photo uploads, config-file recovery, journal-write failures,
replayed Home journals, oversized bitmap allocations and stale compiler output. Regression checks
cover the Python recovery paths and Java decode sizing. The provider's Android behavior still needs
runtime testing; neither a source review nor these tests substitutes for it.

## Physical TV checks

The development TV is a Sony BRAVIA KD-65X85J on Android 12 / API 31. No device is marked fully
supported. The following checks used ADB, not a person operating the remote:

- Installed the signed APK and verified the installed file's SHA-256 against the build.
- Uploaded 12 full-resolution 3840×2160 JPEGs and committed them after checksum verification.
- Opened the launcher, checked its layout and D-pad focus, and launched Netflix.
- Opened the HDMI picker and selected PlayStation 5; Sony's TV app reported HDMI 4. The console's
  actual video picture still needs confirmation.
- Selected StillTV Photos as the screensaver, started it, and captured two different photos with
  the clock in different corners. Sony's preview API crashed before selection; normal dreaming
  worked after selecting the service.
- Tried Home replacement. Sony acknowledged the setting but continued resolving Home to Google TV.
  The handover refused and restored the saved Home/accessibility settings, including Projectivy.
- Restarted the TV. StillTV and its photos remained installed and the app opened successfully.
  The old Home/accessibility setup remained intact, but the selected screensaver reverted to the
  previous Aerial Views service. Persistent screensaver activation is not verified.
- The TV's existing Android UI override is 1920×1080 despite its 4K panel. The photos are 4K files;
  these checks do not establish native 4K UI output. No display override was changed.

## Still needs checking

- Launch apps and return using the physical remote.
- Switch HDMI inputs and confirm the actual picture.
- Start the screensaver, let it rotate, and exit using the remote.
- Resolve Sony's default-Home restriction without silently disabling its stock launcher.
- Verify the provider's permissions and recovery from interrupted uploads/config writes on Android.
- Check memory use with 4K photos on the TV's actual UI surface.
- Turn debugging off after setup and recovery checks are complete.

There are no Android instrumentation or emulator tests yet, and no cross-device speed, memory or
boot-time benchmark. Private device records, photos and settings backups are not published.
