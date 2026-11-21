"""Run the Android-free photo sizing checks on a host JDK, not an emulator."""

import os
import subprocess
import tempfile
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    java = Path(os.environ["JAVA_HOME"]) / "bin"
    source = root / "android/src/io/github/ishaan1342/stilltv/PhotoSizing.java"
    test = root / "tests/java/PhotoSizingTest.java"
    with tempfile.TemporaryDirectory(prefix="stilltv-java-") as directory:
        subprocess.run([str(java / "javac"), "-d", directory, str(source), str(test)], check=True)
        subprocess.run(
            [str(java / "java"), "-cp", directory, "io.github.ishaan1342.stilltv.PhotoSizingTest"],
            check=True,
        )


if __name__ == "__main__":
    main()
