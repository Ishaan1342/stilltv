#!/usr/bin/env python3
"""Build the dependency-free native app with official Android SDK build-tools 34.

No Gradle, Maven downloads, prebuilt APK, host configuration changes or device installation.
The local development signing key is generated outside the checkout. Use your own release key
for distribution: this script's APK is for reproducible local builds, not a trusted app-store release.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def build(sdk: Path, jdk: Path, out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".compile-", dir=out) as work:
        return _build(sdk, jdk, out, Path(work))


def _build(sdk: Path, jdk: Path, out: Path, work: Path) -> Path:
    root = Path(__file__).resolve().parents[1]
    tools, jar = sdk / "build-tools/34.0.0", sdk / "platforms/android-34/android.jar"
    if not jar.is_file() or not (jdk / "bin/javac").is_file():
        raise RuntimeError(
            "JDK 17+ and Android platform 34/build-tools 34.0.0 are required. See docs/build.md."
        )
    out.mkdir(parents=True, exist_ok=True)
    env = dict(
        os.environ,
        JAVA_HOME=str(jdk),
        PATH=str(jdk / "bin") + os.pathsep + os.environ.get("PATH", ""),
    )
    run = lambda *args: subprocess.run([str(x) for x in args], check=True, env=env)
    generated, classes, dex = work / "generated", work / "classes", work / "dex"
    for directory in [generated, classes, dex]:
        directory.mkdir(exist_ok=True)
    aapt2 = Path(os.environ.get("STILLTV_AAPT2", tools / "aapt2"))
    zipalign = Path(os.environ.get("STILLTV_ZIPALIGN", tools / "zipalign"))
    run(aapt2, "compile", "--dir", root / "android/res", "-o", out / "resources.zip")
    run(
        aapt2,
        "link",
        "-I",
        jar,
        "--manifest",
        root / "android/AndroidManifest.xml",
        "--java",
        generated,
        "-A",
        root / "android/assets",
        "-o",
        out / "base.apk",
        out / "resources.zip",
    )
    sources = sorted((root / "android/src").rglob("*.java")) + sorted(generated.rglob("*.java"))
    boot = str(jar) + os.pathsep + str(tools / "core-lambda-stubs.jar")
    run(
        jdk / "bin/javac",
        "-encoding",
        "UTF-8",
        "-source",
        "8",
        "-target",
        "8",
        "-bootclasspath",
        boot,
        "-d",
        classes,
        *sources,
    )
    run(
        tools / "d8",
        "--min-api",
        "26",
        "--lib",
        jar,
        "--output",
        dex,
        *sorted(classes.rglob("*.class")),
    )
    shutil.copyfile(out / "base.apk", out / "with-dex.apk")
    with zipfile.ZipFile(out / "with-dex.apk", "a", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(dex.glob("*.dex")):
            archive.write(file, file.name)
    run(zipalign, "-f", "4", out / "with-dex.apk", out / "aligned.apk")
    keydir = (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "stilltv/build-signing"
    )
    keydir.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = keydir / "development.jks"
    if not key.exists():
        run(
            jdk / "bin/keytool",
            "-genkeypair",
            "-keystore",
            key,
            "-storepass",
            "android",
            "-keypass",
            "android",
            "-alias",
            "stilltv-local",
            "-keyalg",
            "RSA",
            "-keysize",
            "2048",
            "-validity",
            "3650",
            "-dname",
            "CN=StillTV local development,O=StillTV,C=XX",
        )
        key.chmod(0o600)
    apk = out / "stilltv.apk"
    run(
        tools / "apksigner",
        "sign",
        "--ks",
        key,
        "--ks-key-alias",
        "stilltv-local",
        "--ks-pass",
        "pass:android",
        "--key-pass",
        "pass:android",
        "--out",
        apk,
        out / "aligned.apk",
    )
    run(tools / "apksigner", "verify", "--verbose", apk)
    print(
        f"APK: {apk}\nBytes: {apk.stat().st_size}\nSHA256: {hashlib.sha256(apk.read_bytes()).hexdigest()}"
    )
    return apk


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sdk",
        type=Path,
        default=os.environ.get("ANDROID_HOME", os.environ.get("ANDROID_SDK_ROOT")),
    )
    parser.add_argument("--jdk", type=Path, default=os.environ.get("JAVA_HOME"))
    parser.add_argument(
        "--out", type=Path, default=Path(__file__).resolve().parents[1] / "build/android"
    )
    args = parser.parse_args()
    if not args.sdk or not args.jdk:
        parser.error("Set JAVA_HOME and ANDROID_HOME, or pass --jdk and --sdk.")
    try:
        build(args.sdk.expanduser().resolve(), args.jdk.expanduser().resolve(), args.out.resolve())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        sys.exit(1)
