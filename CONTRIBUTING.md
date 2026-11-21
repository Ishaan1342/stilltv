# Contributing

Small PRs are easier to review. Describe the problem, how to reproduce it and what you changed.
Run the checks in the README before opening a PR.

Please use made-up device data in tests and issues. Don't upload inventories, ADB keys, settings
backups, personal photos or account screenshots.

For Android changes, build the APK. If you've tested on a TV, include the model, Android version
and what you tried, without serial numbers or network addresses. Say plainly when something is
only covered by a fake-ADB test or a build check. Home and HDMI changes need real remote testing.

Profiles should name the manufacturer/model and give a reason for each candidate package.
No wildcards or bypasses for protected components. A new profile stays unverified until someone
has tested it on the relevant hardware.

Keep dependencies small. The launcher should stay offline, without telemetry, root or firmware
changes. For changes to recovery, read [the architecture notes](docs/architecture.md) and add tests
for failure cases, especially commands that succeed before their acknowledgement is lost.

Contributions use the MIT license. Credit other projects where they're used.
