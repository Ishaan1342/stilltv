import contextlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from stilltv.core import (
    Adb,
    Refused,
    apply,
    atomic_json,
    digest,
    input_summary,
    inventory,
    plan,
    protected,
    restore,
)


class FakeTV:
    """Stateful fake ADB boundary: tests exercise real planning/journaling/recovery code."""

    def __init__(self):
        self.pkgs = {
            "com.vendor.recommendations",
            "com.vendor.promotions",
            "com.android.settings",
            "com.vendor.tvinput",
            "com.example.home",
        }
        self.disabled = set()
        self.serial = "synthetic-device-A"
        self.writes = []
        self.fail = None
        self.lost_ack = None
        self.home = "com.example.home/.Main"
        self.services = "null"

    def shell(self, *args, **kwargs):
        a = list(args)
        if a[0] == "getprop":
            return {
                "ro.serialno": self.serial,
                "ro.product.model": "Synthetic TV",
                "ro.product.manufacturer": "Example",
                "ro.build.version.sdk": "31",
            }.get(a[1], "")
        if a[:3] == ["pm", "list", "features"]:
            return "feature:android.software.leanback"
        if a[:3] == ["pm", "list", "packages"]:
            return "\n".join(
                "package:" + p for p in sorted(self.disabled if "-d" in a else self.pkgs)
            )
        if a[0] == "cmd":
            return self.home
        if a[:3] == ["settings", "get", "secure"]:
            return self.services
        if a[:2] == ["settings", "list"]:
            return "private_synthetic_setting=not_for_publication"
        if a[0] == "dumpsys":
            return "CEC: display_name: PlayStation 5 power_status: 0 physical_address: 0x4000 port_id: 4"
        if a[:2] in [["pm", "disable-user"], ["pm", "enable"]]:
            pkg = a[-1]
            self.writes.append(a)
            if pkg == self.fail and a[1] == "disable-user":
                raise Refused("Synthetic TV refusal")
            if a[1] == "disable-user":
                self.disabled.add(pkg)
            else:
                self.disabled.discard(pkg)
            if pkg == self.lost_ack and a[1] == "disable-user":
                raise Refused("Simulated acknowledgement loss")
            return "new state: " + ("disabled-user" if a[1] == "disable-user" else "enabled")
        raise AssertionError(a)


def profile(*pkgs):
    return {
        "schema": 1,
        "match": {"manufacturer": "Example"},
        "disable": [
            {"package": p, "reason": "Reviewed synthetic recommendations package; no TV role."}
            for p in pkgs
        ],
    }


class Transactions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "state"
        self.tv = FakeTV()

    def tearDown(self):
        self.tmp.cleanup()

    def planned(self, *pkgs):
        return plan(inventory(self.tv), profile(*pkgs))

    def test_plan_is_read_only(self):
        p = self.planned("com.vendor.recommendations")
        self.assertEqual(len(p["changes"]), 1)
        self.assertEqual(self.tv.writes, [])

    def test_wrong_device_never_writes(self):
        p = self.planned("com.vendor.recommendations")
        self.tv.serial = "synthetic-device-B"
        with self.assertRaisesRegex(Refused, "Wrong hardware"):
            apply(self.tv, p, p["approval"], self.root)
        self.assertEqual(self.tv.writes, [])

    def test_stale_plan_never_writes(self):
        p = self.planned("com.vendor.recommendations")
        self.tv.pkgs.add("com.example.newapp")
        with self.assertRaisesRegex(Refused, "state changed"):
            apply(self.tv, p, p["approval"], self.root)
        self.assertEqual(self.tv.writes, [])

    def test_tampered_plan_never_writes(self):
        p = self.planned("com.vendor.recommendations")
        p["changes"][0]["package"] = "com.vendor.promotions"
        with self.assertRaisesRegex(Refused, "Approval"):
            apply(self.tv, p, p["approval"], self.root)
        self.assertEqual(self.tv.writes, [])

    def test_explicit_digest_required(self):
        p = self.planned("com.vendor.recommendations")
        with self.assertRaises(Refused):
            apply(self.tv, p, "yes", self.root)

    def test_core_and_tv_packages_blocked(self):
        inv = inventory(self.tv)
        for pkg in [
            "android",
            "com.android.settings",
            "com.google.android.gms",
            "com.sony.dtv.tvx",
            "com.vendor.tvinput",
            "com.vendor.updater",
            "com.example.home",
            "com.vendor.bluetooth",
        ]:
            self.assertTrue(protected(pkg, inv), pkg)

    def test_protected_recomputed_even_when_plan_rehashed(self):
        p = self.planned("com.vendor.recommendations")
        p["changes"][0]["package"] = "com.android.settings"
        p["approval"] = digest({k: v for k, v in p.items() if k != "approval"})
        with self.assertRaisesRegex(Refused, "protected"):
            apply(self.tv, p, p["approval"], self.root)

    def test_other_manufacturer_refused(self):
        value = profile()
        value["match"]["manufacturer"] = "Other"
        with self.assertRaises(Refused):
            plan(inventory(self.tv), value)

    def test_other_sdk_profile_refused(self):
        value = profile()
        value["match"]["sdk"] = 34
        with self.assertRaises(Refused):
            plan(inventory(self.tv), value)

    def test_malformed_profiles_refused_without_writes(self):
        for value in [
            [],
            None,
            {"schema": 1, "match": {"manufacturer": 1}},
            {"schema": 1, "match": {"manufacturer": "Example"}, "disable": ["not-an-object"]},
        ]:
            with self.assertRaises(Refused):
                plan(inventory(self.tv), value)
        self.assertEqual(self.tv.writes, [])

    def test_missing_package_refused(self):
        with self.assertRaises(Refused):
            self.planned("com.example.absent")

    def test_duplicate_package_refused(self):
        with self.assertRaises(Refused):
            self.planned("com.vendor.promotions", "com.vendor.promotions")

    def test_review_reason_required(self):
        value = profile("com.vendor.promotions")
        value["disable"][0]["reason"] = "ad"
        with self.assertRaises(Refused):
            plan(inventory(self.tv), value)

    def test_already_disabled_is_not_owned_by_us(self):
        self.tv.disabled.add("com.vendor.recommendations")
        p = self.planned("com.vendor.recommendations")
        self.assertEqual(p["changes"], [])

    def test_apply_idempotent(self):
        p = self.planned("com.vendor.recommendations")
        a = apply(self.tv, p, p["approval"], self.root)
        self.assertEqual(a["status"], "applied")
        b = apply(self.tv, p, p["approval"], self.root)
        self.assertEqual(b["status"], "already_applied")
        self.assertEqual(len(self.tv.writes), 1)

    def test_fresh_plan_after_restore_has_its_own_journal(self):
        first = self.planned("com.vendor.recommendations")
        result = apply(self.tv, first, first["approval"], self.root)
        restore(self.tv, Path(result["journal"]))
        fresh = self.planned("com.vendor.recommendations")
        self.assertNotEqual(first["approval"], fresh["approval"])
        again = apply(self.tv, fresh, fresh["approval"], self.root)
        self.assertNotEqual(result["journal"], again["journal"])
        self.assertEqual(self.tv.disabled, {"com.vendor.recommendations"})

    def test_state_is_reread_after_lock_acquisition(self):
        value = self.planned("com.vendor.recommendations")

        @contextlib.contextmanager
        def changed_while_waiting(*args):
            self.tv.pkgs.add("com.example.newapp")
            yield

        with patch("stilltv.core.device_lock", changed_while_waiting):
            with self.assertRaisesRegex(Refused, "state changed"):
                apply(self.tv, value, value["approval"], self.root)
        self.assertEqual(self.tv.writes, [])

    def test_restore_preserves_preexisting_disabled(self):
        self.tv.disabled.add("com.vendor.promotions")
        p = self.planned("com.vendor.recommendations")
        result = apply(self.tv, p, p["approval"], self.root)
        restore(self.tv, Path(result["journal"]))
        self.assertEqual(self.tv.disabled, {"com.vendor.promotions"})

    def test_mid_batch_failure_compensates(self):
        p = self.planned("com.vendor.recommendations", "com.vendor.promotions")
        self.tv.fail = "com.vendor.promotions"
        with self.assertRaisesRegex(Refused, "rolled back"):
            apply(self.tv, p, p["approval"], self.root)
        self.assertEqual(self.tv.disabled, set())
        self.assertEqual(
            json.loads(next(self.root.rglob("journal.json")).read_text())["status"], "rolled_back"
        )

    def test_lost_acknowledgement_recovers_pending_write(self):
        p = self.planned("com.vendor.recommendations")
        self.tv.lost_ack = "com.vendor.recommendations"
        with self.assertRaisesRegex(Refused, "rolled back"):
            apply(self.tv, p, p["approval"], self.root)
        self.assertEqual(self.tv.disabled, set())

    def test_journal_disk_failure_does_not_prevent_compensation(self):
        value = self.planned("com.vendor.recommendations")

        def disk_full_after_device_write(path, data):
            if self.tv.writes:
                raise OSError("Synthetic disk full")
            atomic_json(path, data)

        with patch("stilltv.core.atomic_json", disk_full_after_device_write):
            with self.assertRaisesRegex(Refused, "Journal:"):
                apply(self.tv, value, value["approval"], self.root)
        self.assertEqual(self.tv.disabled, set())
        path = next(self.root.rglob("journal.json"))
        # The durable pending record is still sufficient for another recovery attempt.
        self.assertEqual(restore(self.tv, path)["status"], "rolled_back")

    def test_recovery_attempts_other_packages_after_one_failure(self):
        value = self.planned("com.vendor.recommendations", "com.vendor.promotions")
        result = apply(self.tv, value, value["approval"], self.root)
        original = self.tv.shell

        def fail_one_restore(*args, **kwargs):
            if args[:2] == ("pm", "enable") and args[-1] == "com.vendor.promotions":
                raise Refused("Synthetic package restore refusal")
            return original(*args, **kwargs)

        self.tv.shell = fail_one_restore
        with self.assertRaisesRegex(Refused, "Recovery incomplete"):
            restore(self.tv, Path(result["journal"]))
        self.assertEqual(self.tv.disabled, {"com.vendor.promotions"})
        self.tv.shell = original
        restore(self.tv, Path(result["journal"]))
        self.assertEqual(self.tv.disabled, set())

    def test_final_journal_save_failure_compensates(self):
        value = self.planned("com.vendor.recommendations")

        def fail_final_status(path, data):
            if data.get("status") == "applied":
                raise OSError("Synthetic final journal failure")
            atomic_json(path, data)

        with patch("stilltv.core.atomic_json", fail_final_status):
            with self.assertRaisesRegex(Refused, "recorded changes rolled back.*Journal:"):
                apply(self.tv, value, value["approval"], self.root)
        self.assertEqual(self.tv.disabled, set())
        journal = json.loads(next(self.root.rglob("journal.json")).read_text())
        self.assertEqual(journal["status"], "rolled_back")

    def test_wrong_device_restore_refused(self):
        p = self.planned("com.vendor.recommendations")
        r = apply(self.tv, p, p["approval"], self.root)
        self.tv.serial = "another-TV"
        with self.assertRaises(Refused):
            restore(self.tv, Path(r["journal"]))
        self.assertIn("com.vendor.recommendations", self.tv.disabled)

    def test_journal_cannot_restore_unplanned_package(self):
        p = self.planned("com.vendor.recommendations")
        r = apply(self.tv, p, p["approval"], self.root)
        path = Path(r["journal"])
        j = json.loads(path.read_text())
        j["steps"].append({"package": "com.vendor.promotions", "status": "pending"})
        path.write_text(json.dumps(j))
        with self.assertRaisesRegex(Refused, "outside"):
            restore(self.tv, path)

    def test_held_device_lock_refused(self):
        p = self.planned("com.vendor.recommendations")
        self.root.mkdir()
        (self.root / (p["device_id"] + ".lock")).mkdir()
        with self.assertRaisesRegex(Refused, "lock"):
            apply(self.tv, p, p["approval"], self.root)
        self.assertEqual(self.tv.writes, [])

    @unittest.skipUnless(os.name == "posix", "POSIX file mode check")
    def test_state_backup_private_permissions(self):
        p = self.planned("com.vendor.recommendations")
        r = apply(self.tv, p, p["approval"], self.root)
        self.assertEqual(Path(r["journal"]).stat().st_mode & 0o777, 0o600)

    def test_unsupported_sdk_refused(self):
        original = self.tv.shell
        self.tv.shell = lambda *a, **k: (
            "25" if a == ("getprop", "ro.build.version.sdk") else original(*a, **k)
        )
        with self.assertRaises(Refused):
            inventory(self.tv)

    def test_empty_serial_refused(self):
        self.tv.serial = ""
        with self.assertRaises(Refused):
            inventory(self.tv)

    def test_empty_home_resolution_refused(self):
        self.tv.home = ""
        with self.assertRaisesRegex(Refused, "resolve the current Home"):
            inventory(self.tv)
        self.assertEqual(self.tv.writes, [])

    def test_hdmi4_mapping_not_row_number(self):
        x = input_summary(
            "CEC: display_name: PlayStation 5 power_status: -1 physical_address: 0x4000 port_id: 4"
        )
        self.assertEqual(x, [{"port": 4, "label": "PlayStation 5", "power_status": -1}])

    def test_host_command_injection_refused(self):
        for value in ["-s other", "tv; touch x", "$(id)", "tv\nreboot"]:
            with self.assertRaises(Refused):
                Adb(value)

    def test_remote_shell_arguments_quoted(self):
        adb = Adb("synthetic-tv")
        with patch.object(adb, "command", return_value="ok") as run:
            adb.shell("example", "two words", "$(not-executed)")
            self.assertEqual(
                run.call_args.args[0], ["shell", "example 'two words' '$(not-executed)'"]
            )


if __name__ == "__main__":
    unittest.main()
