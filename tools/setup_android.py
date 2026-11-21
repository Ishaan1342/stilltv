"""Bootstrap a specified Linux Android SDK for a clean build host, verifying Google's archive.

Run with JDK 17 configured. Downloads only from dl.google.com. SDK license acceptance is an explicit
flag, not a hidden side effect of building. This tool does not modify shell configuration or any TV.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

URL = "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
# Archive also verified against Google's repository2-1.xml SHA-1
# d313adb7aedccf6cf0cfca51ec180f0059f5f8f8 before recording this SHA-256.
SHA256 = "2d2d50857e4eb553af5a6dc3ad507a17adf43d115264b1afc116f95c92e5e258"


def setup(sdk: Path, accept_licenses: bool) -> None:
    if os.name != "posix":
        raise RuntimeError(
            "This bootstrap archive is Linux-only; use your platform's official SDK manager."
        )
    sdk.mkdir(parents=True, exist_ok=True)
    archive = sdk / "command-tools-12.zip"
    manager = sdk / "cmdline-tools/12.0/bin/sdkmanager"
    if not manager.is_file():
        partial = archive.with_suffix(".partial")
        with urllib.request.urlopen(URL, timeout=60) as response, partial.open("wb") as target:
            shutil.copyfileobj(response, target)
        checksum = hashlib.sha256()
        with partial.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                checksum.update(chunk)
        if checksum.hexdigest() != SHA256:
            raise RuntimeError("Android command tools checksum mismatch; nothing extracted")
        partial.replace(archive)
        destination = sdk / "cmdline-tools/12.0"
        with zipfile.ZipFile(archive) as source:
            for entry in source.infolist():
                parts = Path(entry.filename).parts
                if not parts or parts[0] != "cmdline-tools" or ".." in parts:
                    raise RuntimeError("Unexpected archive path")
                if entry.is_dir():
                    continue
                target = destination.joinpath(*parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(entry) as input_file, target.open("wb") as output:
                    shutil.copyfileobj(input_file, output)
                mode = (entry.external_attr >> 16) & 0o777
                if mode:
                    target.chmod(mode)
        manager.chmod(0o755)
    command = [str(manager), "--sdk_root=" + str(sdk)]
    if accept_licenses:
        result = subprocess.run(
            command + ["--licenses"],
            input="y\n" * 100,
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
        if result.returncode:
            raise RuntimeError("SDK license step failed: " + result.stderr[-1200:])
    result = subprocess.run(
        command + ["platforms;android-34", "build-tools;34.0.0"],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode:
        raise RuntimeError("SDK install failed: " + (result.stdout + result.stderr)[-2500:])
    for required in ["platforms/android-34/android.jar", "build-tools/34.0.0/aapt2"]:
        if not (sdk / required).is_file():
            raise RuntimeError("SDK installation incomplete: " + required)
    print("Verified command-tools archive; Android platform 34 and build-tools 34.0.0 ready")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument(
        "--accept-licenses",
        action="store_true",
        help="Explicitly accept the Android SDK licenses on this build host",
    )
    args = parser.parse_args()
    setup(args.sdk.expanduser().resolve(), args.accept_licenses)
