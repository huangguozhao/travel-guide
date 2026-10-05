import json
import tempfile
import unittest
from pathlib import Path

from validate_trip_data import validate


def valid_data(detail="rich"):
    return {
        "schema_version": 1,
        "meta": {
            "title": "测试行程",
            "detail": detail,
            "audience": "同行朋友",
            "as_of": "2026-10-05",
            "required_sections": ["timeline", "maps", "sources"],
        },
        "stops": [
            {
                "id": "a",
                "order": 1,
                "name": "A",
                "role": "core",
                "summary": "现场",
                "why_go": "值得",
                "arrival": "入口",
                "duration_min": 30,
                "leave_when": "完成后",
                "map_ref": "map-a-b",
                "source_ids": ["src"],
                "media_ids": ["photo-a"],
            },
            {
                "id": "b",
                "order": 2,
                "name": "B",
                "role": "core",
                "summary": "现场",
                "why_go": "值得",
                "arrival": "入口",
                "duration_min": 40,
                "leave_when": "完成后",
                "map_ref": "map-a-b",
                "source_ids": ["src"],
                "media_ids": ["photo-b"],
            },
        ],
        "legs": [
            {
                "id": "a-b",
                "from": "a",
                "to": "b",
                "mode": "walk",
                "duration_min": 10,
                "status": "estimated",
                "source_ids": ["src"],
                "map_media_id": "map-a-b",
            }
        ],
        "routes": [{"id": "main", "label": "主路线", "primary": True, "stop_ids": ["a", "b"], "leg_ids": ["a-b"]}],
        "timeline": [{"id": "t-a", "label": "A", "stop_id": "a"}, {"id": "t-b", "label": "B", "stop_id": "b"}],
        "media": [
            {"id": "photo-a", "type": "photo", "subject_stop_id": "a", "subject_verified": True, "source_url": "https://example.com/a", "author": "x", "license": "CC", "usage": "压缩", "local_path": "a.jpg", "caption": "A"},
            {"id": "photo-b", "type": "photo", "subject_stop_id": "b", "subject_verified": True, "source_url": "https://example.com/b", "author": "x", "license": "CC", "usage": "压缩", "local_path": "b.jpg", "caption": "B"},
            {"id": "map-a-b", "type": "map", "subject_stop_ids": ["a", "b"], "subject_verified": True, "source_url": "https://example.com/map", "local_path": "map.jpg", "caption": "路线"},
        ],
        "sources": [{"id": "src", "title": "来源", "url": "https://example.com", "accessed_on": "2026-10-05", "status": "verified"}],
        "fallbacks": [{"trigger": "下雨", "action": "缩短路线"}],
    }


class TripDataValidationTests(unittest.TestCase):
    def test_valid_rich_data_passes(self):
        result = validate(valid_data())
        self.assertTrue(result["ok"], result["errors"])

    def test_rich_requires_real_photo_per_core_stop(self):
        data = valid_data()
        data["stops"][1]["media_ids"] = []
        result = validate(data)
        self.assertFalse(result["ok"])
        self.assertTrue(any("no subject-verified real photo" in error for error in result["errors"]))

    def test_route_leg_must_connect_consecutive_stops(self):
        data = valid_data()
        data["legs"][0]["to"] = "a"
        result = validate(data)
        self.assertFalse(result["ok"])
        self.assertTrue(any("does not connect consecutive stops" in error for error in result["errors"]))

    def test_html_coverage_is_checked(self):
        data = valid_data()
        with tempfile.TemporaryDirectory() as tmp:
            html = Path(tmp) / "guide.html"
            html.write_text('<section data-stop-id="a"><img data-media-id="photo-a"></section>', encoding="utf-8")
            result = validate(data, html)
        self.assertFalse(result["ok"])
        self.assertTrue(any("HTML missing core data-stop-id" in error for error in result["errors"]))
        self.assertTrue(any("HTML missing data-media-id" in error for error in result["errors"]))

    def test_standard_does_not_require_photo_per_core_stop(self):
        data = valid_data("standard")
        data["stops"][1]["media_ids"] = []
        result = validate(data)
        self.assertTrue(result["ok"], result["errors"])


if __name__ == "__main__":
    unittest.main()
