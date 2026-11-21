"""Explicit, JSON-reporting command line. No shell session, fleet auto-discovery or hidden writes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import (
    Adb,
    Refused,
    apply,
    atomic_json,
    inventory,
    plan,
    private_path,
    restore,
    state_root,
)
from .launcher import activate, configure, install, restore_home


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="stilltv",
        description="Set up an Android TV home screen, prepare photos, and manage saved changes.",
    )
    parser.add_argument("--device", help="Exact authorized ADB device serial or host:port")
    parser.add_argument(
        "--state-dir", type=Path, help="Private state directory outside any Git checkout"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inspect", help="Read-only hardware, package and HDMI inventory")
    p = commands.add_parser("plan", help="Read-only plan; no device writes")
    p.add_argument("--profile", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = commands.add_parser("apply", help="Apply only an explicitly approved, fresh plan")
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--approve", required=True)
    p = commands.add_parser(
        "restore", help="Recover this tool's package changes from a private journal"
    )
    p.add_argument("--journal", type=Path, required=True)
    p = commands.add_parser("photos", help="Offline photo preparation; no TV connection")
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--width", type=int, default=3840)
    p.add_argument("--height", type=int, default=2160)
    p.add_argument(
        "--layout",
        choices=["contain", "fill"],
        default="contain",
        help="Keep the whole photo (contain), or crop landscapes to fill the screen (fill)",
    )
    p = commands.add_parser(
        "install", help="Install a locally built APK; do not change Home or interrupt playback"
    )
    p.add_argument("--apk", type=Path, required=True)
    p = commands.add_parser("configure", help="Upload photos and save the home-screen config")
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--photos", type=Path)
    p = commands.add_parser(
        "activate", help="Change Home with saved rollback; requires an explicit flag"
    )
    p.add_argument("--confirm-home-change", action="store_true", required=True)
    p.add_argument(
        "--pause-projectivy",
        action="store_true",
        help="Pause only Projectivy's existing Home override, preserving other services",
    )
    p = commands.add_parser(
        "restore-home", help="Restore the original Home and accessibility settings"
    )
    p.add_argument("--journal", type=Path, required=True)
    commands.add_parser("open", help="Open StillTV once; does not change default Home")
    args = parser.parse_args(argv)
    try:
        if args.command == "photos":
            from .photos import prepare

            result = prepare(args.source, args.out, args.width, args.height, args.layout)
        else:
            if not args.device:
                parser.error("--device is required for TV operations")
            adb = Adb(args.device)
            if args.command == "inspect":
                result = inventory(adb)
            elif args.command == "plan":
                target = private_path(args.out)
                result = plan(inventory(adb), json.loads(args.profile.read_text()))
                if target.exists():
                    raise Refused("Plan output already exists; choose a new filename.")
                atomic_json(target, result)
            elif args.command == "apply":
                result = apply(
                    adb,
                    json.loads(args.plan.read_text()),
                    args.approve,
                    args.state_dir or state_root(),
                )
            elif args.command == "restore":
                result = restore(adb, args.journal)
            elif args.command == "install":
                result = install(adb, args.apk)
            elif args.command == "configure":
                result = configure(
                    adb, json.loads(args.config.read_text()), args.photos, args.state_dir
                )
            elif args.command == "activate":
                result = activate(adb, args.state_dir or state_root(), args.pause_projectivy)
            elif args.command == "restore-home":
                result = restore_home(adb, args.journal)
            else:
                inventory(adb)
                from .core import APP

                result = {
                    "status": "opened",
                    "response": adb.shell("am", "start", "-W", "-n", APP + "/.MainActivity"),
                }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (Refused, OSError, ValueError, KeyError, TypeError) as error:
        print(
            json.dumps({"status": "refused", "reason": str(error)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
