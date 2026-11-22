import hashlib
import tempfile
import unittest
from pathlib import Path

from test_transactions import FakeTV

from stilltv.core import APP, Refused
from stilltv.launcher import configure, install


class UploadTV(FakeTV):
    def __init__(self):
        super().__init__()
        self.pkgs.add(APP)
        self.uploads = []
        self.reject_photo = False
        self.interrupt_photo = False

    def shell(self, *args, **kwargs):
        if args[0] == "content":
            self.uploads.append((args, kwargs.get("data")))
            if args[1] == "write" and "/photo/" in args[-1] and self.interrupt_photo:
                raise Refused("Connection lost mid-upload")
            if args[1] == "call":
                if args[5] == "commit-photo" and self.reject_photo:
                    return "Bundle[{error=Incomplete photo upload}]"
                return "Bundle[{result=ok}]"
            return ""
        return super().shell(*args, **kwargs)


class Configuration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.photos = self.root / "photos"
        self.photos.mkdir()
        self.name = "home-" + "a" * 64 + ".jpg"
        self.dream = "dream-" + "a" * 64 + ".jpg"
        for name in (self.name, self.dream):
            (self.photos / name).write_bytes(b"test image bytes")
        self.config = {
            "schema": 1,
            "favorites": [],
            "photos": [{"file": self.name, "dream": self.dream}],
        }
        self.tv = UploadTV()

    def tearDown(self):
        self.tmp.cleanup()

    def run_configure(self):
        return configure(self.tv, self.config, self.photos, self.root / "state")

    def test_config_is_committed_only_after_checked_photo_uploads(self):
        self.run_configure()
        uploads = self.tv.uploads
        self.assertEqual(len(uploads), 6)
        photo_uri = uploads[0][0][-1]
        token = photo_uri.split("/")[-2]
        self.assertEqual(len(token), 32)
        expected = f"{token}:{self.name}:{hashlib.sha256(b'test image bytes').hexdigest()}"
        self.assertEqual(uploads[1][0][-1], expected)
        self.assertTrue(uploads[-2][0][-1].endswith("/pending/" + token))
        self.assertEqual(uploads[-1][0][-3:], ("commit", "--arg", token))

    def test_failed_photo_check_never_commits_config(self):
        self.tv.reject_photo = True
        with self.assertRaisesRegex(Refused, "upload was rejected"):
            self.run_configure()
        self.assertEqual(len(self.tv.uploads), 2)

    def test_interrupted_upload_never_writes_an_active_photo_path(self):
        self.tv.interrupt_photo = True
        with self.assertRaisesRegex(Refused, "Connection lost"):
            self.run_configure()
        self.assertEqual(len(self.tv.uploads), 1)
        uri = self.tv.uploads[0][0][-1]
        self.assertEqual(len(uri.split("/photo/")[1].split("/")), 2)

    def test_all_inputs_are_checked_before_any_upload(self):
        (self.photos / self.dream).unlink()
        with self.assertRaises(Refused):
            self.run_configure()
        self.assertEqual(self.tv.uploads, [])

    def test_install_accepts_adb_progress_before_success(self):
        apk = self.root / "stilltv.apk"
        apk.write_bytes(b"synthetic APK")
        self.tv.command = lambda args: "Performing Streamed Install\nSuccess"
        self.assertEqual(install(self.tv, apk)["status"], "installed")

    def test_install_requires_a_standalone_success_acknowledgement(self):
        apk = self.root / "stilltv.apk"
        apk.write_bytes(b"synthetic APK")
        self.tv.command = lambda args: "Installation unsuccessful"
        with self.assertRaisesRegex(Refused, "not acknowledged"):
            install(self.tv, apk)
