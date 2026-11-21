"""Check tracked publication files, not private working directories. This is not a complete secret scanner."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
    files = [Path(p.decode()) for p in raw.split(b"\0") if p]
    if not files:
        raise RuntimeError("No tracked files to audit; stage the intended source files first")
    blocked = {
        ".venv",
        "backup",
        "backups",
        "private",
        "shots",
        ".state",
        ".stilltv",
        "build",
        "dist",
    }
    patterns = [
        ("private key", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
        ("GitHub credential", re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}")),
        ("GitHub fine-grained credential", re.compile(rb"github_pat_[A-Za-z0-9_]{40,}")),
        ("device/network address", re.compile(rb"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
        ("MAC address", re.compile(rb"\b(?:[a-fA-F0-9]{2}:){5}[a-fA-F0-9]{2}\b")),
    ]
    problems = []
    for path in files:
        if (
            blocked.intersection(path.parts)
            or path.suffix in {".apk", ".jks", ".keystore", ".aab"}
            or path.name.startswith("adbkey")
        ):
            problems.append(f"Forbidden publication path: {path}")
        data = (root / path).read_bytes()
        for label, pattern in patterns:
            if pattern.search(data):
                problems.append(f"Potential {label} in {path}; inspect privately")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print(
        f"Public-tree audit passed for {len(files)} tracked files. Manual content/history review still required."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
