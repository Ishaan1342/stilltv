# Verification record

## Local development checks, 21 November 2026

- Python 3.13 / ARM64 Linux: **42 unit and failure-injection tests passed**.
- Ruff import/static checks and formatting: passed.
- Android platform 34 + build-tools 34.0.0, ARM64 Temurin JDK 17 with native Debian aapt2/zipalign:
  native Java compilation, DEX generation, resource packaging and APK signature verification passed.
- First signed development APK: **25,242 bytes**. Size is not a speed/efficiency benchmark; future
  revisions may differ. Contains no bundled personal photos or third-party runtime libraries.
- Source distribution and wheel build: passed; the sdist includes Android source, build tools and docs.
- Installed-wheel smoke in a fresh virtual environment outside the checkout: passed.
- Read-only inventory and zero-change planning on the Sony development TV: passed; HDMI/CEC identifies
  PlayStation 5 on port 4. No launcher activation or package cleanup is implied by that read-only check.
- Independent CI results are attached to each exact commit in [GitHub Actions](https://github.com/Ishaan1342/stilltv/actions/workflows/ci.yml).

## Hardware status

The initial development TV is a Sony BRAVIA KD-65X85J on Android 12 / API 31. Its existing setup has
provided useful HDMI/setup failure evidence. **That is not yet a StillTV launcher validation.**

Until a deliberate StillTV test is completed, do not mark any device as fully supported. Required:

- Open StillTV without replacing Home; verify native rendering and D-pad focus.
- Open a streaming app, return with the actual remote, and verify favorites/library behavior.
- Discover inputs and display the actual HDMI source; a recorded CEC name is not picture verification.
- Test the screensaver with several local frames, exit it with the remote, and check idle behavior.
- Activate Home only at an agreed moment, check the physical Home/Input buttons, and exercise recovery.
- Restart deliberately and verify Home, HDMI and the remote again.
- Disable debugging and verify network-debug ports closed only when recovery checks are done.

Fake-TV tests are transaction tests, **not an emulator or a real TV**. GitHub Android builds are compile/
packaging checks, not instrumented UI tests. No cross-device performance, memory or boot-time benchmark
has been run. We do not publish private screenshots, device addresses or settings backups as evidence.
