"""Install/configure are separate from taking over Home. No stock app is disabled."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path

from .core import (
    APP,
    AUTHORITY,
    Adb,
    Refused,
    atomic_json,
    device_lock,
    inventory,
    private_path,
    state_root,
)


def validate_config(config: dict) -> None:
    if not isinstance(config, dict):
        raise Refused("Launcher configuration must be a JSON object.")
    if config.get("schema") != 1 or config.get("theme", "cinematic") not in {
        "cinematic",
        "quiet",
        "contrast",
    }:
        raise Refused("Invalid launcher configuration version or theme.")
    if not isinstance(config.get("name", ""), str) or len(config.get("name", "")) > 48:
        raise Refused("Greeting must be at most 48 characters.")
    for key, default, low, high in [
        ("rotation_seconds", 300, 30, 3600),
        ("dream_seconds", 20, 10, 300),
    ]:
        n = config.get(key, default)
        if type(n) is not int or not low <= n <= high:
            raise Refused("Slideshow intervals are outside allowed bounds.")
    favorites = config.get("favorites")
    if not isinstance(favorites, list) or len(favorites) > 12:
        raise Refused("Supply a favorites list with at most twelve entries.")
    for f in favorites:
        if (
            not isinstance(f, dict)
            or not isinstance(f.get("package"), str)
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+", f["package"])
            or not isinstance(f.get("label"), str)
            or not 1 <= len(f["label"]) <= 32
        ):
            raise Refused("Invalid favorite package or label.")
    photos = config.get("photos", [])
    if not isinstance(photos, list) or len(photos) > 200:
        raise Refused("At most 200 local photos.")
    for p in photos:
        if not isinstance(p, dict) or any(
            not isinstance(p.get(k), str)
            or not re.fullmatch(r"(?:home|dream)-[a-f0-9]{64}\.jpg", p[k])
            for k in ["file", "dream"]
        ):
            raise Refused("Photos must use generated, path-safe local names.")
        if not isinstance(p.get("caption", ""), str) or len(p.get("caption", "")) > 80:
            raise Refused("Caption too long.")


def configure(
    adb: Adb, config: dict, photo_dir: Path | None = None, root: Path | None = None
) -> dict:
    validate_config(config)
    inv = inventory(adb)
    root = private_path(root) if root is not None else state_root()
    with device_lock(root, inv["device_id"]):
        current = inventory(adb)
        if current["device_id"] != inv["device_id"]:
            raise Refused("Device changed while acquiring its lock.")
        return _configure(adb, config, photo_dir, current)


def _configure(adb: Adb, config: dict, photo_dir: Path | None, inv: dict) -> dict:
    if APP not in inv["packages"]:
        raise Refused("Install StillTV before configuring it.")
    blobs = []
    for photo in config.get("photos", []):
        if photo_dir is None:
            raise Refused("Supply the prepared local photo directory.")
        for key in ["file", "dream"]:
            path = photo_dir / photo[key]
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
                raise Refused("A generated photo is missing, oversized or a symlink.")
            blobs.append((photo[key], path))
    # Validate all local inputs before writing any bytes. Active config is committed atomically last.
    upload = uuid.uuid4().hex
    for name, path in dict(blobs).items():
        data = path.read_bytes()
        adb.shell(
            "content",
            "write",
            "--uri",
            f"content://{AUTHORITY}/photo/{upload}/{name}",
            data=data,
        )
        output = adb.shell(
            "content",
            "call",
            "--uri",
            f"content://{AUTHORITY}",
            "--method",
            "commit-photo",
            "--arg",
            f"{upload}:{name}:{hashlib.sha256(data).hexdigest()}",
        )
        if "result=ok" not in output:
            raise Refused(
                "Photo upload was rejected. The previous photos and config are unchanged."
            )
    adb.shell(
        "content",
        "write",
        "--uri",
        f"content://{AUTHORITY}/pending/{upload}",
        data=json.dumps(config).encode(),
    )
    output = adb.shell(
        "content", "call", "--uri", f"content://{AUTHORITY}", "--method", "commit", "--arg", upload
    )
    if "result=ok" not in output:
        raise Refused("Configuration commit was rejected. The previous config remains active.")
    return {
        "status": "configured",
        "device_id": inv["device_id"],
        "photos": len(config.get("photos", [])),
        "restart": "Reopen StillTV to load the new configuration.",
    }


def install(adb: Adb, apk: Path) -> dict:
    inv = inventory(adb)
    if not apk.is_file() or apk.suffix != ".apk":
        raise Refused("Supply a locally built APK.")
    output = adb.command(["install", "-r", str(apk.resolve())])
    if output.strip() != "Success":
        raise Refused("Install was not acknowledged; original Home has not been changed.")
    return {
        "status": "installed",
        "device_id": inv["device_id"],
        "sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
        "home_changed": False,
    }


def activate(adb: Adb, root: Path, pause_projectivy: bool = False) -> dict:
    """Reversible Home handover. Refuse chooser/setup defaults rather than guessing a rollback."""
    root = private_path(root)
    inv = inventory(adb)
    with device_lock(root, inv["device_id"]):
        current = inventory(adb)
        if current["device_id"] != inv["device_id"]:
            raise Refused("Device changed while acquiring its lock.")
        return _activate(adb, root, pause_projectivy, current)


def _activate(adb: Adb, root: Path, pause_projectivy: bool, inv: dict) -> dict:
    if APP not in inv["packages"]:
        raise Refused("StillTV is not installed.")
    if inv["home"].startswith(APP + "/"):
        return {
            "status": "already_home",
            "note": "Verify the physical remote; a saved Home preference is not proof.",
        }
    if (
        not re.fullmatch(r"[\w.]+/[\w.$]+", inv["home"])
        or inv["home"].startswith("android/")
        or re.search(r"setup|resolver|chooser", inv["home"], re.IGNORECASE)
    ):
        raise Refused(
            "Current Home is a chooser/setup screen; finish TV setup and pick a stable Home first."
        )
    path = root / inv["device_id"] / ("home-" + uuid.uuid4().hex + ".json")
    before = {
        "schema": 1,
        "device_id": inv["device_id"],
        "home": inv["home"],
        "accessibility": inv["accessibility"],
        "accessibility_enabled": adb.shell("settings", "get", "secure", "accessibility_enabled"),
        "removed_services": [],
        "status": "pending",
    }
    component = (
        "com.spocky.projengmenu/com.spocky.projengmenu.services.ProjectivyAccessibilityService"
    )
    if pause_projectivy and component in before["accessibility"].split(":"):
        before["removed_services"] = [component]
    atomic_json(path, before)
    try:
        if before["removed_services"]:
            component = "com.spocky.projengmenu/com.spocky.projengmenu.services.ProjectivyAccessibilityService"
            remaining = [
                x for x in before["accessibility"].split(":") if x not in {"", "null", component}
            ]
            if remaining:
                adb.shell(
                    "settings",
                    "put",
                    "secure",
                    "enabled_accessibility_services",
                    ":".join(remaining),
                )
            else:
                adb.shell("settings", "delete", "secure", "enabled_accessibility_services")
                adb.shell("settings", "put", "secure", "accessibility_enabled", "0")
        out = adb.shell(
            "cmd", "package", "set-home-activity", "--user", "0", APP + "/.MainActivity"
        )
        if "Success" not in out:
            raise Refused("TV refused the Home preference.")
        adb.shell("input", "keyevent", "KEYCODE_HOME")
        state = adb.shell("dumpsys", "activity", "activities")
        if not any("mResumedActivity" in line and APP + "/" in line for line in state.splitlines()):
            raise Refused("Home did not reach StillTV.")
        before["status"] = "active"
        atomic_json(path, before)
    except (Exception, KeyboardInterrupt) as error:
        try:
            _restore_home(adb, path, inventory(adb))
        except Exception as recovery:
            raise Refused(
                f"Handover failed; recovery incomplete. Keep ADB available. Journal: {path}"
            ) from recovery
        raise Refused("Handover failed and the original Home settings were restored.") from error
    return {"status": "active", "journal": str(path), "physical_remote_verified": False}


def restore_home(adb: Adb, path: Path) -> dict:
    path = private_path(path)
    inv = inventory(adb)
    with device_lock(path.parents[1], inv["device_id"]):
        current = inventory(adb)
        if current["device_id"] != inv["device_id"]:
            raise Refused("Device changed while acquiring its lock.")
        return _restore_home(adb, path, current)


def _restore_home(adb: Adb, path: Path, inv: dict) -> dict:
    before = json.loads(path.read_text())
    if inv["device_id"] != before.get("device_id"):
        raise Refused("Home journal belongs to another device.")
    if before.get("schema") != 1 or before.get("status") not in {"pending", "active", "restored"}:
        raise Refused("Invalid Home journal version or status.")
    if before["status"] == "restored":
        return {"status": "already_restored", "home": before["home"]}
    if not re.fullmatch(r"[\w.]+/[\w.$]+", before.get("home", "")):
        raise Refused("Invalid original Home component.")
    if inv["home"] != before["home"] and not inv["home"].startswith(APP + "/"):
        raise Refused(
            "Home was changed by another actor. Inspect it rather than overwriting that choice."
        )
    expected = (
        "com.spocky.projengmenu/com.spocky.projengmenu.services.ProjectivyAccessibilityService"
    )
    if any(service != expected for service in before.get("removed_services", [])):
        raise Refused("Unexpected accessibility recovery entry.")
    output = adb.shell("cmd", "package", "set-home-activity", "--user", "0", before["home"])
    if "Success" not in output:
        raise Refused("Original Home preference was refused.")
    # Merge only the service we paused. Never replace newer accessibility choices with an old snapshot.
    current = adb.shell("settings", "get", "secure", "enabled_accessibility_services")
    services = [x for x in current.split(":") if x not in {"", "null"}]
    for service in before.get("removed_services", []):
        if service not in services:
            services.append(service)
    if before.get("removed_services"):
        enabled = adb.shell("settings", "get", "secure", "accessibility_enabled")
        adb.shell("settings", "put", "secure", "enabled_accessibility_services", ":".join(services))
        # Don't enable globally disabled services, or turn off a newer screen reader.
        if before.get("accessibility_enabled") == "1" and enabled != "1":
            adb.shell("settings", "put", "secure", "accessibility_enabled", "1")
    before["status"] = "restored"
    atomic_json(path, before)
    return {"status": "restored", "home": before["home"]}
