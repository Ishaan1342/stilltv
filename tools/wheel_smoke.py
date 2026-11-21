"""Install the built wheel in a fresh environment and run the CLI away from the source tree."""

from __future__ import annotations

import os
import subprocess
import tempfile
import venv
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    wheels = sorted((root / "dist").glob("stilltv-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError("Build exactly one wheel into dist/ before running the smoke test")
    with tempfile.TemporaryDirectory(prefix="stilltv-wheel-") as work:
        env_dir = Path(work) / "venv"
        venv.EnvBuilder(with_pip=True).create(env_dir)
        python = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        subprocess.run(
            [str(python), "-m", "pip", "install", "--no-deps", str(wheels[0])],
            check=True,
            cwd=work,
            env=env,
        )
        subprocess.run(
            [
                str(python),
                "-I",
                "-c",
                "from stilltv.cli import main; raise SystemExit(main(['--help']))",
            ],
            check=True,
            cwd=work,
            env=env,
        )
        check = subprocess.run(
            [
                str(python),
                "-I",
                "-c",
                "from stilltv.cli import main; raise SystemExit(main(['inspect']))",
            ],
            cwd=work,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if check.returncode != 2 or "--device is required" not in check.stderr:
            raise RuntimeError("Installed CLI did not enforce an explicit device")
        subprocess.run(
            [
                str(python),
                "-I",
                "-c",
                "import stilltv; print('Installed wheel:', stilltv.__file__)",
            ],
            check=True,
            cwd=work,
            env=env,
        )
    print("Isolated installed-wheel smoke passed")


if __name__ == "__main__":
    main()
