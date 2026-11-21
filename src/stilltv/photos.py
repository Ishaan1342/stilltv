"""Offline photo framing: keep the entire photo away from text and zoom cutoffs.

No face-recognition claim: the foreground is contained, never face-cropped. No EXIF, GPS,
original filename or photo bytes are uploaded. Pillow is an optional dependency.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .core import Refused, atomic_json, private_path


def prepare(source: Path, output: Path, width: int = 3840, height: int = 2160) -> dict:
    try:
        from PIL import Image, ImageFilter, ImageOps, ImageStat
    except ImportError as error:
        raise Refused('Install the optional photo tools: pip install "stilltv[photos]"') from error
    if (
        width < 640
        or height < 360
        or width > 7680
        or height > 4320
        or abs(width / height - 16 / 9) > 0.01
    ):
        raise Refused("Use a 16:9 frame from 640×360 through 7680×4320.")
    output = private_path(output)
    source = source.expanduser().resolve()
    if not source.is_dir() or source == output or source in output.parents:
        raise Refused(
            "Use a photo directory and an output directory outside the source and Git checkouts."
        )
    files = sorted(
        f
        for f in source.iterdir()
        if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )
    if not files or len(files) > 200:
        raise Refused(
            "Supply between 1 and 200 photos. Nested folders and symlinks are not followed."
        )
    if any(f.is_symlink() for f in files):
        raise Refused("Symlinked photos are not accepted.")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    result = []
    for file in files:
        with Image.open(file) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
        # Always contain the whole foreground. The blurred background may be cropped.
        backdrop = ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS)
        backdrop = backdrop.filter(ImageFilter.GaussianBlur(radius=max(8, width // 80)))
        key = hashlib.sha256(
            image.tobytes() + str(image.size).encode() + f"{width}x{height}:v1".encode()
        ).hexdigest()
        names = {}
        for mode, sx, sy, cy in [("home", 0.76, 0.54, 0.49), ("dream", 0.76, 0.76, 0.50)]:
            frame = backdrop.copy()
            foreground = ImageOps.contain(
                image, (int(width * sx), int(height * sy)), method=Image.Resampling.LANCZOS
            )
            frame.paste(
                foreground,
                ((width - foreground.width) // 2, int(height * cy - foreground.height / 2)),
            )
            name = f"{mode}-{key}.jpg"
            frame.save(output / name, "JPEG", quality=92, optimize=True, exif=b"")
            names[mode] = name
        brightness = sum(ImageStat.Stat(image.resize((64, 64))).mean) / 3
        result.append(
            {
                "file": names["home"],
                "dream": names["dream"],
                "caption": "",
                "night": brightness < 110,
            }
        )
    manifest = {
        "schema": 1,
        "frame": [width, height],
        "photos": result,
        "method": "contain-full-foreground-v1",
    }
    atomic_json(output / "photos.json", manifest)
    return manifest
