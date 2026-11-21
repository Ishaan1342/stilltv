# Building Android

Prerequisites: JDK 17, Android SDK platform `android-34`, build-tools `34.0.0`. Obtain them from the
[Android SDK](https://developer.android.com/studio#command-tools) and an official JDK distributor.
Use their published checksums. SDK licenses apply; neither SDK nor JDK is redistributed in this repo.

On an existing SDK installation:

```bash
sdkmanager 'platforms;android-34' 'build-tools;34.0.0'
export JAVA_HOME=/path/to/jdk-17
export ANDROID_HOME=/path/to/android-sdk
python tools/build_android.py
```

On a clean Linux x86-64 build host, `python tools/setup_android.py --sdk /path/to/sdk` can bootstrap
the official command tools and specified packages. It verifies a pinned SHA-256 before extraction.
Review the Android SDK terms and pass `--accept-licenses` explicitly when appropriate. CI uses this
path instead of assuming its runner image contains an SDK manager. An ARM64 host still needs native
aapt2/zipalign overrides below, because Google's Linux native build binaries are x86-64.

The script compiles resources with aapt2, compiles Java against the Android API and SDK lambda stubs,
uses d8 for DEX, zipaligns, signs with a per-host local development key, then runs apksigner verification.
It does not install anything on a TV. APK output is `build/android/stilltv.apk` with a printed SHA-256.

The SDK build-tools binaries for Linux are x86-64. On ARM64 Linux, install native `aapt` (which includes
`aapt2`) and `zipalign` from your OS distribution and use an ARM64 JDK. Pass their paths explicitly:

```bash
STILLTV_AAPT2=/usr/bin/aapt2 STILLTV_ZIPALIGN=/usr/bin/zipalign python tools/build_android.py
```

If using locally extracted OS packages, also set `LD_LIBRARY_PATH` for their dependencies. This is a
build-process override only; don't rewrite shell or service configuration. d8/apksigner are Java and
remain portable. Windows/macOS native APK builds have not been verified; Linux CI is the reference.

Development key: `$XDG_STATE_HOME/stilltv/build-signing/development.jks` or
`~/.local/state/stilltv/build-signing/development.jks`. Never commit it. The development key uses the
standard non-secret development password `android`; its privacy comes from the private file, not that
password. Rebuilding on another machine creates a different signing identity, so an existing install
cannot be updated by that other key. Use a deliberately managed release key for production distribution.

This project does not claim bit-for-bit reproducible signed APKs. The source/build procedure and API/
tool versions are specified; signing keys and ZIP timestamps vary. CI verifies compilation/signatures.
