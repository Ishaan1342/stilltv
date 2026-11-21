import tempfile
import unittest
from pathlib import Path

from test_transactions import FakeTV

from stilltv.core import APP, Refused
from stilltv.launcher import activate, restore_home

HELPER = "com.spocky.projengmenu/com.spocky.projengmenu.services.ProjectivyAccessibilityService"
READER = "com.example.reader/.Service"


class HomeTV(FakeTV):
    def __init__(self):
        super().__init__()
        self.pkgs.add(APP)
        self.services = HELPER + ":" + READER
        self.fail_home = False
        self.enabled = "1"

    def shell(self, *a, **kwargs):
        if a[:3] == ("cmd", "package", "set-home-activity"):
            self.home = a[-1]
            self.writes.append(a)
            return "Success"
        if a[:3] == ("settings", "get", "secure") and a[3] == "accessibility_enabled":
            return self.enabled
        if a[:3] == ("settings", "put", "secure"):
            if a[3] == "enabled_accessibility_services":
                self.services = a[4]
            elif a[3] == "accessibility_enabled":
                self.enabled = a[4]
            self.writes.append(a)
            return ""
        if a[:3] == ("settings", "delete", "secure"):
            if a[3] == "enabled_accessibility_services":
                self.services = "null"
            self.writes.append(a)
            return ""
        if a[:2] == ("input", "keyevent"):
            return ""
        if a[:3] == ("dumpsys", "activity", "activities"):
            return "mResumedActivity: " + (
                "com.other.app/.Activity" if self.fail_home else self.home
            )
        return super().shell(*a, **kwargs)


class HomeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "state"
        self.tv = HomeTV()

    def tearDown(self):
        self.tmp.cleanup()

    def test_handover_preserves_screenreader(self):
        result = activate(self.tv, self.root, True)
        self.assertEqual(result["status"], "active")
        self.assertEqual(self.tv.services, READER)
        self.assertFalse(result["physical_remote_verified"])

    def test_restore_merges_new_services(self):
        result = activate(self.tv, self.root, True)
        self.tv.services += ":com.example.newreader/.Service"
        restore_home(self.tv, Path(result["journal"]))
        self.assertEqual(
            set(self.tv.services.split(":")), {READER, HELPER, "com.example.newreader/.Service"}
        )
        self.assertEqual(self.tv.home, "com.example.home/.Main")

    def test_failed_handover_rolls_back(self):
        self.tv.fail_home = True
        with self.assertRaisesRegex(Refused, "original Home settings were restored"):
            activate(self.tv, self.root, True)
        self.assertEqual(self.tv.home, "com.example.home/.Main")
        self.assertIn(HELPER, self.tv.services)

    def test_wrong_device_restore_never_writes(self):
        result = activate(self.tv, self.root, True)
        n = len(self.tv.writes)
        self.tv.serial = "another-TV"
        with self.assertRaises(Refused):
            restore_home(self.tv, Path(result["journal"]))
        self.assertEqual(len(self.tv.writes), n)

    def test_restore_wont_overwrite_a_new_home_choice(self):
        result = activate(self.tv, self.root, True)
        self.tv.home = "com.example.newhome/.Main"
        n = len(self.tv.writes)
        with self.assertRaisesRegex(Refused, "another actor"):
            restore_home(self.tv, Path(result["journal"]))
        self.assertEqual(len(self.tv.writes), n)

    def test_can_activate_again_after_restore(self):
        result = activate(self.tv, self.root, True)
        restore_home(self.tv, Path(result["journal"]))
        again = activate(self.tv, self.root, True)
        self.assertNotEqual(result["journal"], again["journal"])

    def test_replaying_restored_journal_preserves_later_accessibility_choice(self):
        result = activate(self.tv, self.root, True)
        path = Path(result["journal"])
        restore_home(self.tv, path)
        self.tv.services = READER
        count = len(self.tv.writes)
        self.assertEqual(restore_home(self.tv, path)["status"], "already_restored")
        self.assertEqual(len(self.tv.writes), count)
        self.assertEqual(self.tv.services, READER)

    def test_replaying_old_restored_journal_does_not_undo_new_activation(self):
        result = activate(self.tv, self.root, True)
        path = Path(result["journal"])
        restore_home(self.tv, path)
        activate(self.tv, self.root, True)
        count = len(self.tv.writes)
        restore_home(self.tv, path)
        self.assertEqual(len(self.tv.writes), count)
        self.assertTrue(self.tv.home.startswith(APP + "/"))

    def test_setup_home_refused_without_writes(self):
        self.tv.home = "com.example.setup/.Main"
        with self.assertRaises(Refused):
            activate(self.tv, self.root)
        self.assertEqual(self.tv.writes, [])

    def test_android_resolver_home_refused_without_writes(self):
        self.tv.home = "android/com.android.internal.app.ResolverActivity"
        with self.assertRaises(Refused):
            activate(self.tv, self.root)
        self.assertEqual(self.tv.writes, [])

    def test_pause_does_not_touch_accessibility_without_projectivy(self):
        self.tv.services = READER
        result = activate(self.tv, self.root, True)
        restore_home(self.tv, Path(result["journal"]))
        self.assertEqual(self.tv.services, READER)
        self.assertFalse(any(x[0] == "settings" for x in self.tv.writes))

    def test_restore_preserves_original_global_accessibility_disabled(self):
        self.tv.services = HELPER
        self.tv.enabled = "0"
        result = activate(self.tv, self.root, True)
        restore_home(self.tv, Path(result["journal"]))
        self.assertEqual(self.tv.services, HELPER)
        self.assertEqual(self.tv.enabled, "0")

    def test_restore_keeps_a_new_reader_globally_enabled(self):
        self.tv.services = HELPER
        self.tv.enabled = "0"
        result = activate(self.tv, self.root, True)
        self.tv.services = READER
        self.tv.enabled = "1"
        restore_home(self.tv, Path(result["journal"]))
        self.assertEqual(set(self.tv.services.split(":")), {HELPER, READER})
        self.assertEqual(self.tv.enabled, "1")


if __name__ == "__main__":
    unittest.main()
