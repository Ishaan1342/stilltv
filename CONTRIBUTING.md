# Contributing

Prefer a small reproducible case and one change per PR. Do not attach your TV inventory, ADB keys,
logs, personal photo library or account screenshots. Use synthetic fixtures like the test suite.

Run the README checks. Changes to Android source need a clean APK build and a clearly identified
hardware test (model, API level, actions checked; no serial/IP/account). Don't call an emulator or a
fake ADB test a hardware check. Changes to Home/HDMI behavior need physical remote observations.

Device profiles must identify manufacturer/model, provide a specific review reason per candidate,
and default conservatively. No wildcard disabling. No force bypass for protected components.
New profiles are **unverified** until their documented hardware check is complete.

Keep runtime dependencies small and optional. No network permission, telemetry, root, factory/service
menus, app uninstallation or automated firmware changes in the launcher/workflow.

See `docs/architecture.md` before changing recovery. Test refusals and lost acknowledgements, not only
happy paths. MIT license applies to contributions. Be respectful; credit upstream work accurately.
