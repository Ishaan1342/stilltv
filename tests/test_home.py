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

    def shell(self, *a, **kwargs):
        if a[:3] == ("cmd", "package", "set-home-activity"):
            self.home = a[-1]
            self.writes.append(a)
            return "Success"
        if a[:3] == ("settings", "get", "secure") and a[3] == "accessibility_enabled":
            return "1"
        if a[:3] == ("settings", "put", "secure"):
            if a[3] == "enabled_accessibility_services":
                self.services = a[4]
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

    def test_setup_home_refused_without_writes(self):
        self.tv.home = "com.example.setup/.Main"
        with self.assertRaises(Refused):
            activate(self.tv, self.root)
        self.assertEqual(self.tv.writes, [])


if __name__ == "__main__":
    unittest.main()
