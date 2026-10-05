"""Behavior tests for the offline packer. Run with Python; no network needed."""
import base64
import importlib.util
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("html_bundle", Path(__file__).with_name("html_bundle.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+yNioAAAAASUVORK5CYII=")
PAGE = '<!doctype html><html><head><title>Test</title><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><h1>Trip</h1>{}</body></html>'


class BundleTests(unittest.TestCase):
    def test_embeds_real_file_and_validates(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "图.png").write_bytes(PNG)
            text, count = MODULE.bundle(PAGE.format('<img alt="Map" src="{{asset:图.png}}"><a href="https://example.com/info">Source</a>'), root)
            report = MODULE.audit_text(text)
            self.assertEqual(count, 1)
            self.assertTrue(report["ok"])
            self.assertEqual(report["embedded_images"], 1)
            self.assertNotIn("{{asset:", text)

    def test_rejects_escape_from_asset_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "inside").mkdir()
            (root / "outside.png").write_bytes(PNG)
            with self.assertRaises(ValueError):
                MODULE.bundle('{{asset:../outside.png}}', root / "inside")

    def test_rejects_wrong_file_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bad.png").write_text("not an image", encoding="utf-8")
            with self.assertRaises(ValueError):
                MODULE.bundle('{{asset:bad.png}}', root)

    def test_detects_missing_link_and_duplicate_id(self):
        report = MODULE.audit_text(PAGE.format('<p id="stop">A</p><p id="stop">B</p><a href="#gone">Go</a>'))
        self.assertFalse(report["ok"])
        self.assertIn("Duplicate id: stop", report["errors"])
        self.assertIn("Missing internal link target: gone", report["errors"])

    def test_blocks_non_portable_resources_but_allows_citations(self):
        for resource in ['<img alt="x" src="https://example.com/map.jpg">',
                         '<script src="assets/app.js"></script>',
                         '<style>p{background:url(assets/map.png)}</style>',
                         '<style>@import "https://example.com/style.css";</style>']:
            self.assertFalse(MODULE.audit_text(PAGE.format(resource))["ok"])
        self.assertTrue(MODULE.audit_text(PAGE.format('<a href="https://example.com/info">Info</a>'))["ok"])

    def test_rejects_corrupt_embedded_image(self):
        report = MODULE.audit_text(PAGE.format('<img alt="x" src="data:image/png;base64,%%%%">'))
        self.assertFalse(report["ok"])

    def test_handles_dynamic_image_without_claiming_it_loaded(self):
        report = MODULE.audit_text(PAGE.format('<img id="drawer-image" alt="Map">'))
        self.assertTrue(report["ok"])
        self.assertIn("Image has no initial source; verify dynamic loading", report["warnings"])

    def test_refuses_unintentional_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "output.html"
            MODULE.write_new(target, "original")
            with self.assertRaises(FileExistsError):
                MODULE.write_new(target, "changed")
            self.assertEqual(target.read_text(encoding="utf-8"), "original")


if __name__ == "__main__":
    unittest.main()
