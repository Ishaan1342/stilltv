import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from stilltv.core import Refused, private_path
from stilltv.launcher import validate_config
from stilltv.photos import prepare

ROOT = Path(__file__).resolve().parents[1]


class Assets(unittest.TestCase):
    def test_bundled_config_is_valid(self):
        validate_config(json.loads((ROOT / "android/assets/config.json").read_text()))

    def test_traversal_photo_rejected(self):
        config = {
            "schema": 1,
            "favorites": [],
            "photos": [{"file": "../../private.jpg", "dream": "evil"}],
        }
        with self.assertRaises(Refused):
            validate_config(config)

    def test_excessive_config_rate_rejected(self):
        with self.assertRaises(Refused):
            validate_config({"schema": 1, "favorites": [], "rotation_seconds": 1})

    def test_injection_package_rejected(self):
        with self.assertRaises(Refused):
            validate_config({"schema": 1, "favorites": [{"package": "x;reboot", "label": "bad"}]})

    def test_private_data_refused_in_git_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            with self.assertRaises(Refused):
                private_path(root / "nested/deeper/device.json")

    def test_no_network_or_sensitive_launcher_permissions(self):
        root = ET.parse(ROOT / "android/AndroidManifest.xml").getroot()
        self.assertEqual(root.findall("uses-permission"), [])
        provider = root.find("application/provider")
        self.assertEqual(
            provider.get("{http://schemas.android.com/apk/res/android}permission"),
            "android.permission.WRITE_SECURE_SETTINGS",
        )

    def test_photos_keep_foreground_and_strip_metadata(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Install the photos extra")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            output = Path(directory) / "prepared"
            image = Image.new("RGB", (100, 200), "red")
            exif = Image.Exif()
            exif[270] = "private caption"
            image.save(source / "private-personal-name.jpg", exif=exif)
            result = prepare(source, output, 640, 360)
            self.assertEqual(len(result["photos"]), 1)
            for entry in result["photos"]:
                self.assertNotIn("private", str(entry))
                for key in ["file", "dream"]:
                    with Image.open(output / entry[key]) as frame:
                        self.assertEqual(frame.size, (640, 360))
                        self.assertEqual(len(frame.getexif()), 0)
                        pixel = frame.getpixel((320, 180))
                        self.assertGreater(pixel[0], 200)

    def test_output_cannot_be_inside_photo_source(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(Refused):
                prepare(Path(directory), Path(directory) / "output", 640, 360)


if __name__ == "__main__":
    unittest.main()
