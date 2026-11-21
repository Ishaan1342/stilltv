# What has been tested

Last checked: 21 November 2026.

## Local checks

- 61 Python tests pass on Python 3.13 / ARM64 Linux. These include wrong-device and stale-plan
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
  That does not test the launcher, HDMI switching or Home replacement.

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

## Still needs a TV test

The development TV is a Sony BRAVIA KD-65X85J on Android 12 / API 31. StillTV has not been installed
or activated on it yet. No device is marked fully supported.

- Open the app and check layout, photo rotation and D-pad focus.
- Launch apps and return using the physical remote.
- Switch HDMI inputs and confirm the actual picture.
- Start the screensaver, let it rotate, and exit using the remote.
- Check Home replacement and recovery, then repeat after a restart.
- Verify the provider's permissions and recovery from interrupted uploads/config writes on Android.
- Check memory use with 4K photos on the TV's actual UI surface.
- Turn debugging off after setup and recovery checks are complete.

There are no Android instrumentation or emulator tests yet, and no cross-device speed, memory or
boot-time benchmark. Private device records, photos and settings backups are not published.
