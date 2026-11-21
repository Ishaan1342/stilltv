"""Device identity, policy, write-ahead journal and compensating recovery.

Not an Android firmware backup. Journals restore only changes made by this tool.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shlex
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

PACKAGE = re.compile(r"[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+")
PROTECTED_WORDS = re.compile(
    r"input|tvx|tuner|launcher|setup|upgrade|update|bluetooth|remote|keyboard|"
    r"cast|airplay|assistant|store|permission|system|provider|wifi|network|accessibility",
    re.IGNORECASE,
)
APP = "io.github.ishaan1342.stilltv"
AUTHORITY = APP + ".config"


class Refused(RuntimeError):
    """An unsafe, stale, refused or ambiguous operation. Never automatically retried."""


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        if os.name == "posix":
            dfd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def private_path(path: Path) -> Path:
    """Refuse private output anywhere within a Git checkout, including nested paths."""
    path = path.expanduser().resolve()
    if any((p / ".git").exists() for p in [path, *path.parents]):
        raise Refused("Private device records/photos must be outside a Git checkout.")
    return path


def state_root() -> Path:
    return private_path(
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "stilltv"
    )


class Adb:
    def __init__(self, device: str, executable: str = "adb", timeout: int = 15):
        if (
            not device
            or device.startswith("-")
            or not re.fullmatch(r"[A-Za-z0-9_.:\[\]-]+", device)
        ):
            raise Refused(
                "Use an explicit ADB serial or host:port; options and shell syntax are not accepted."
            )
        self.device, self.executable, self.timeout = device, executable, timeout

    def command(self, args: list[str], data: bytes | None = None) -> str:
        try:
            result = subprocess.run(
                [self.executable, "-s", self.device, *args],
                input=data,
                capture_output=True,
                timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise Refused(
                f"ADB unavailable or timed out; outcome may be unknown: {type(exc).__name__}"
            ) from exc
        text = result.stdout.decode(errors="replace")
        error = result.stderr.decode(errors="replace")
        if result.returncode or re.search(
            r"(?:^|\n)(?:Error:|Exception |Failure |Security exception:|Permission Denial:)|SecurityException",
            text,
            re.IGNORECASE,
        ):
            raise Refused((error or text).strip()[:600] or "ADB refused the operation.")
        return text.strip()

    def shell(self, *args: str, data: bytes | None = None) -> str:
        # adb shell joins argv remotely. Quote for THAT shell, not just the host.
        return self.command(["shell", shlex.join(args)], data)


def packages(output: str) -> list[str]:
    return sorted({line[8:].strip() for line in output.splitlines() if line.startswith("package:")})


def input_summary(output: str) -> list[dict[str, Any]]:
    found = {}
    for line in output.splitlines():
        m = re.search(r"display_name: (.*?) power_status: (-?\d+).*?port_id: (\d+)", line)
        if m and int(m[3]) > 0:
            found[(int(m[3]), m[1])] = {"port": int(m[3]), "label": m[1], "power_status": int(m[2])}
    return sorted(found.values(), key=lambda x: (x["port"], x["label"]))


def inventory(adb: Adb) -> dict[str, Any]:
    prop = lambda name: adb.shell("getprop", name)
    serial = prop("ro.serialno") or prop("ro.boot.serialno")
    if not serial or serial.lower() in {"unknown", "null"}:
        raise Refused(
            "No stable hardware serial available. Device-bound writes cannot be made safely."
        )
    installed = packages(adb.shell("pm", "list", "packages", "--user", "0"))
    disabled = packages(adb.shell("pm", "list", "packages", "-d", "--user", "0"))
    if not installed:
        raise Refused("Empty package inventory; refusing to treat a failed read as an empty TV.")
    sdk = prop("ro.build.version.sdk")
    if not sdk.isdigit() or int(sdk) < 26:
        raise Refused("StillTV requires Android TV 8 / API 26 or newer.")
    model, manufacturer = prop("ro.product.model"), prop("ro.product.manufacturer")
    tv_features = adb.shell("pm", "list", "features")
    if not any(
        x in tv_features for x in ["android.software.leanback", "android.hardware.type.television"]
    ):
        raise Refused("This device does not advertise Android TV features.")
    home_lines = adb.shell(
        "cmd",
        "package",
        "resolve-activity",
        "--brief",
        "-a",
        "android.intent.action.MAIN",
        "-c",
        "android.intent.category.HOME",
    ).splitlines()
    if not home_lines:
        raise Refused("Could not resolve the current Home app; nothing changed.")
    home = home_lines[-1]
    services = adb.shell("settings", "get", "secure", "enabled_accessibility_services")
    result = {
        "schema": 1,
        "device_id": hashlib.sha256((manufacturer + "\0" + serial).encode()).hexdigest(),
        "model": model,
        "manufacturer": manufacturer,
        "sdk": int(sdk),
        "packages": installed,
        "disabled": disabled,
        "home": home,
        "accessibility": services,
    }
    result["snapshot"] = digest(result)
    result["inputs"] = input_summary(adb.shell("dumpsys", "tv_input"))
    return result


def protected(package: str, inv: dict[str, Any]) -> bool:
    current = inv["home"].split("/")[0]
    services = {x.split("/")[0] for x in inv["accessibility"].split(":")}
    return (
        package in {"android", APP, current, *services}
        or package.startswith(("com.android.", "com.google.", "android.", "org.chromium."))
        or bool(PROTECTED_WORDS.search(package))
    )


def plan(inv: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(profile, dict) or profile.get("schema") != 1:
        raise Refused("Unsupported profile schema.")
    match = profile.get("match", {})
    if (
        not isinstance(match, dict)
        or not isinstance(match.get("manufacturer"), str)
        or not match["manufacturer"]
    ):
        raise Refused("A profile must explicitly match a manufacturer.")
    if match["manufacturer"].casefold() != inv["manufacturer"].casefold():
        raise Refused("Profile manufacturer does not match this device.")
    if match.get("model") and match["model"] != inv["model"]:
        raise Refused("Profile model does not match this device.")
    if match.get("sdk") is not None and match["sdk"] != inv["sdk"]:
        raise Refused("Profile Android API level does not match this device.")
    changes, seen = [], set()
    entries = profile.get("disable", [])
    if not isinstance(entries, list):
        raise Refused("Disable candidates must be a list.")
    for entry in entries:
        if not isinstance(entry, dict):
            raise Refused("Every disable candidate must be an object.")
        pkg, reason = entry.get("package", ""), entry.get("reason", "")
        if not PACKAGE.fullmatch(pkg) or not isinstance(reason, str) or len(reason.strip()) < 20:
            raise Refused(
                "Every candidate needs a valid package and a specific review reason (20+ characters)."
            )
        if pkg in seen:
            raise Refused("Duplicate candidate package.")
        seen.add(pkg)
        if protected(pkg, inv):
            raise Refused(f"Protected package: {pkg}. There is no force override.")
        if pkg not in inv["packages"]:
            raise Refused(f"Candidate package is not installed: {pkg}")
        if pkg not in inv["disabled"]:
            changes.append(
                {"package": pkg, "before": "enabled", "after": "disabled-user", "reason": reason}
            )
    body = {
        "schema": 1,
        "plan_id": uuid.uuid4().hex,
        "device_id": inv["device_id"],
        "snapshot": inv["snapshot"],
        "model": inv["model"],
        "changes": changes,
    }
    return {**body, "approval": digest(body)}


def validate_plan(value: dict[str, Any], inv: dict[str, Any], approval: str) -> None:
    if not isinstance(value, dict) or not isinstance(value.get("changes"), list):
        raise Refused("Malformed plan.")
    body = {k: v for k, v in value.items() if k != "approval"}
    if value.get("schema") != 1 or approval != value.get("approval") or approval != digest(body):
        raise Refused("Approval must match the complete, unmodified plan SHA-256.")
    if value.get("device_id") != inv["device_id"]:
        raise Refused("Wrong hardware device; nothing changed.")
    seen = set()
    for change in value.get("changes", []):
        if not isinstance(change, dict):
            raise Refused("Malformed transition.")
        pkg = change.get("package", "")
        if not PACKAGE.fullmatch(pkg) or protected(pkg, inv) or pkg in seen:
            raise Refused("Plan contains a protected, invalid or duplicate package.")
        if change.get("before") != "enabled" or change.get("after") != "disabled-user":
            raise Refused("Unsupported transition in plan.")
        seen.add(pkg)


@contextlib.contextmanager
def device_lock(root: Path, device_id: str):
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = root / (device_id + ".lock")
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise Refused(
            "Another operation or interrupted process owns the device lock. Inspect it before removing it."
        ) from exc
    try:
        yield
    finally:
        lock.rmdir()


def is_disabled(adb: Adb, package: str) -> bool:
    output = packages(adb.shell("pm", "list", "packages", "-d", "--user", "0"))
    return package in output


def recover(adb: Adb, journal: dict[str, Any], path: Path) -> dict[str, Any]:
    failures = []
    for step in reversed(journal["steps"]):
        if step["status"] == "restored":
            continue
        pkg = step["package"]
        # A write-ahead step can have succeeded even if ADB never returned an acknowledgement.
        try:
            if is_disabled(adb, pkg):
                adb.shell("pm", "enable", "--user", "0", pkg)
                if is_disabled(adb, pkg):
                    raise Refused("Rollback verification failed.")
            step["status"] = "restored"
        except Exception as error:
            # One unavailable package must not prevent attempts to restore the others.
            failures.append(error)
        try:
            atomic_json(path, journal)
        except OSError:
            # The pending write is already recorded. A full disk must not prevent compensation.
            pass
    journal["status"] = "recovery_required" if failures else "rolled_back"
    try:
        atomic_json(path, journal)
    except OSError as error:
        state = "Recovery incomplete" if failures else "Changes restored, but journal save failed"
        raise Refused(
            f"{state}. Keep this journal and debugging available. Journal: {path}"
        ) from error
    if failures:
        raise Refused(
            f"Recovery incomplete. Keep debugging available. Journal: {path}"
        ) from failures[0]
    return journal


def apply(adb: Adb, value: dict[str, Any], approval: str, root: Path) -> dict[str, Any]:
    root = private_path(root)
    inv = inventory(adb)
    validate_plan(value, inv, approval)
    path = root / value["device_id"] / value["approval"] / "journal.json"
    with device_lock(root, inv["device_id"]):
        current = inventory(adb)
        if current["device_id"] != inv["device_id"]:
            raise Refused("Device changed while acquiring its lock.")
        inv = current
        validate_plan(value, inv, approval)
        if path.exists():
            old = json.loads(path.read_text())
            if old["status"] == "applied" and all(
                is_disabled(adb, c["package"]) for c in value["changes"]
            ):
                return {"status": "already_applied", "journal": str(path)}
            raise Refused(
                "This plan already has a journal; restore it before creating a fresh plan."
            )
        if inv["snapshot"] != value["snapshot"]:
            raise Refused("Device state changed since planning. Inspect and create a fresh plan.")
        journal = {
            "schema": 1,
            "status": "applying",
            "device_id": inv["device_id"],
            "plan": value,
            "before": inv,
            "steps": [],
        }
        atomic_json(path, journal)
        # Back up settings locally before the first write; they may contain private account data.
        backup = {
            namespace: adb.shell("settings", "list", namespace)
            for namespace in ["secure", "global", "system"]
        }
        atomic_json(path.parent / "settings-backup.json", backup)
        try:
            for change in value["changes"]:
                step = {"package": change["package"], "status": "pending"}
                journal["steps"].append(step)
                atomic_json(path, journal)
                adb.shell("pm", "disable-user", "--user", "0", change["package"])
                if not is_disabled(adb, change["package"]):
                    raise Refused("Package change was not verified.")
                step["status"] = "applied"
                atomic_json(path, journal)
            journal["status"] = "applied"
            atomic_json(path, journal)
        except (Exception, KeyboardInterrupt) as exc:
            journal["status"] = "recovery_required"
            try:
                atomic_json(path, journal)
            except OSError:
                pass  # Still try to restore the device when journal storage is unavailable.
            try:
                recover(adb, journal, path)
            except (Exception, KeyboardInterrupt) as rollback_error:
                raise Refused(
                    f"Change failed and recovery is incomplete. Journal: {path}"
                ) from rollback_error
            raise Refused(f"Change failed; recorded changes rolled back. Journal: {path}") from exc
    return {"status": "applied", "journal": str(path), "changes": len(value["changes"])}


def restore(adb: Adb, path: Path) -> dict[str, Any]:
    path = private_path(path)
    inv = inventory(adb)
    with device_lock(path.parents[2], inv["device_id"]):
        current = inventory(adb)
        if current["device_id"] != inv["device_id"]:
            raise Refused("Device changed while acquiring its lock.")
        return _restore(adb, path, current)


def _restore(adb: Adb, path: Path, inv: dict[str, Any]) -> dict[str, Any]:
    journal = json.loads(path.read_text())
    value = journal.get("plan", {})
    validate_plan(value, inv, value.get("approval", ""))
    if journal.get("device_id") != inv["device_id"]:
        raise Refused("Journal belongs to different hardware.")
    allowed = {c["package"] for c in value["changes"]}
    if any(s.get("package") not in allowed for s in journal.get("steps", [])):
        raise Refused("Journal contains a step outside its approved plan.")
    for pkg in allowed:
        if pkg not in inv["packages"]:
            raise Refused("A recorded package is missing; manual recovery is required.")
    recover(adb, journal, path)
    return {"status": "rolled_back", "journal": str(path)}
