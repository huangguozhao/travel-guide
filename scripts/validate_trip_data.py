#!/usr/bin/env python3
"""Validate travel-guide trip-data and optional rendered HTML coverage."""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


DETAILS = {"standard", "rich"}
SOURCE_STATES = {"verified", "estimated", "unknown", "login_required"}
STOP_ROLES = {"core", "optional", "fallback"}
MEDIA_TYPES = {"photo", "map", "illustration", "screenshot"}
PLACEHOLDER_RE = re.compile(r"\b(?:TODO|TBD|PLACEHOLDER)\b", re.I)


class CoverageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stop_ids: set[str] = set()
        self.media_ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        stop_id = attr_map.get("data-stop-id")
        media_id = attr_map.get("data-media-id")
        if stop_id:
            self.stop_ids.add(stop_id)
        if media_id:
            self.media_ids.add(media_id)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"trip-data file not found: {path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from None


def require_text(obj: dict[str, Any], key: str, where: str, errors: list[str]) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{where}.{key} must be a non-empty string")
        return ""
    if PLACEHOLDER_RE.search(value):
        errors.append(f"{where}.{key} contains an unfinished placeholder")
    return value.strip()


def require_list(obj: dict[str, Any], key: str, where: str, errors: list[str]) -> list[Any]:
    value = obj.get(key)
    if not isinstance(value, list):
        errors.append(f"{where}.{key} must be an array")
        return []
    return value


def unique_index(items: list[Any], label: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        where = f"{label}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where} must be an object")
            continue
        item_id = require_text(item, "id", where, errors)
        if not item_id:
            continue
        if item_id in result:
            errors.append(f"duplicate {label} id: {item_id}")
        else:
            result[item_id] = item
    return result


def validate(data: Any, html_path: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return {"ok": False, "errors": ["root must be an object"], "warnings": []}

    if data.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    meta = data.get("meta")
    if not isinstance(meta, dict):
        errors.append("meta must be an object")
        meta = {}
    require_text(meta, "title", "meta", errors)
    detail = require_text(meta, "detail", "meta", errors)
    if detail not in DETAILS:
        errors.append("meta.detail must be standard or rich")
    require_text(meta, "audience", "meta", errors)
    require_text(meta, "as_of", "meta", errors)
    required_sections = require_list(meta, "required_sections", "meta", errors)
    if not required_sections:
        errors.append("meta.required_sections must not be empty")

    stops = require_list(data, "stops", "root", errors)
    legs = require_list(data, "legs", "root", errors)
    routes = require_list(data, "routes", "root", errors)
    timeline = require_list(data, "timeline", "root", errors)
    media = require_list(data, "media", "root", errors)
    sources = require_list(data, "sources", "root", errors)
    fallbacks = require_list(data, "fallbacks", "root", errors)

    stop_by_id = unique_index(stops, "stops", errors)
    leg_by_id = unique_index(legs, "legs", errors)
    media_by_id = unique_index(media, "media", errors)
    source_by_id = unique_index(sources, "sources", errors)
    unique_index(routes, "routes", errors)
    unique_index(timeline, "timeline", errors)

    for source_id, source in source_by_id.items():
        where = f"sources[{source_id}]"
        require_text(source, "title", where, errors)
        require_text(source, "url", where, errors)
        require_text(source, "accessed_on", where, errors)
        state = require_text(source, "status", where, errors)
        if state not in SOURCE_STATES:
            errors.append(f"{where}.status must be one of {sorted(SOURCE_STATES)}")

    for media_id, item in media_by_id.items():
        where = f"media[{media_id}]"
        media_type = require_text(item, "type", where, errors)
        if media_type not in MEDIA_TYPES:
            errors.append(f"{where}.type must be one of {sorted(MEDIA_TYPES)}")
        subject_id = require_text(item, "subject_stop_id", where, errors)
        if subject_id and subject_id not in stop_by_id:
            errors.append(f"{where}.subject_stop_id references unknown stop {subject_id}")
        require_text(item, "source_url", where, errors)
        require_text(item, "caption", where, errors)
        if not item.get("local_path") and not item.get("url"):
            errors.append(f"{where} needs local_path or url")
        if media_type == "photo":
            if item.get("subject_verified") is not True:
                errors.append(f"{where}.subject_verified must be true for a real photo")
            require_text(item, "author", where, errors)
            require_text(item, "license", where, errors)
            require_text(item, "usage", where, errors)

    orders: set[int] = set()
    core_ids: list[str] = []
    for stop_id, stop in stop_by_id.items():
        where = f"stops[{stop_id}]"
        order = stop.get("order")
        if not isinstance(order, int) or order < 1:
            errors.append(f"{where}.order must be a positive integer")
        elif order in orders:
            errors.append(f"duplicate stop order: {order}")
        else:
            orders.add(order)
        require_text(stop, "name", where, errors)
        role = require_text(stop, "role", where, errors)
        if role not in STOP_ROLES:
            errors.append(f"{where}.role must be one of {sorted(STOP_ROLES)}")
        if role == "core":
            core_ids.append(stop_id)
            for key in ("summary", "why_go", "arrival", "leave_when", "map_ref"):
                require_text(stop, key, where, errors)
            duration = stop.get("duration_min")
            if not isinstance(duration, (int, float)) or duration <= 0:
                errors.append(f"{where}.duration_min must be greater than 0")
            stop_sources = require_list(stop, "source_ids", where, errors)
            for source_id in stop_sources:
                if source_id not in source_by_id:
                    errors.append(f"{where}.source_ids references unknown source {source_id}")
            media_ids = require_list(stop, "media_ids", where, errors)
            for media_id in media_ids:
                if media_id not in media_by_id:
                    errors.append(f"{where}.media_ids references unknown media {media_id}")
            if detail == "rich":
                real_photos = [
                    media_by_id[mid]
                    for mid in media_ids
                    if mid in media_by_id
                    and media_by_id[mid].get("type") == "photo"
                    and media_by_id[mid].get("subject_verified") is True
                    and media_by_id[mid].get("subject_stop_id") == stop_id
                ]
                if not real_photos:
                    errors.append(f"{where} has no subject-verified real photo for rich output")

    if not core_ids:
        errors.append("at least one core stop is required")

    for leg_id, leg in leg_by_id.items():
        where = f"legs[{leg_id}]"
        from_id = require_text(leg, "from", where, errors)
        to_id = require_text(leg, "to", where, errors)
        if from_id not in stop_by_id:
            errors.append(f"{where}.from references unknown stop {from_id}")
        if to_id not in stop_by_id:
            errors.append(f"{where}.to references unknown stop {to_id}")
        require_text(leg, "mode", where, errors)
        duration = leg.get("duration_min")
        if not isinstance(duration, (int, float)) or duration < 0:
            errors.append(f"{where}.duration_min must be non-negative")
        if "distance_km" in leg and (not isinstance(leg["distance_km"], (int, float)) or leg["distance_km"] < 0):
            errors.append(f"{where}.distance_km must be non-negative")
        state = require_text(leg, "status", where, errors)
        if state not in SOURCE_STATES:
            errors.append(f"{where}.status must be one of {sorted(SOURCE_STATES)}")
        for source_id in require_list(leg, "source_ids", where, errors):
            if source_id not in source_by_id:
                errors.append(f"{where}.source_ids references unknown source {source_id}")
        map_media_id = leg.get("map_media_id")
        if map_media_id and map_media_id not in media_by_id:
            errors.append(f"{where}.map_media_id references unknown media {map_media_id}")

    primary_count = 0
    used_leg_ids: set[str] = set()
    for index, route in enumerate(routes):
        if not isinstance(route, dict):
            continue
        where = f"routes[{index}]"
        if route.get("primary") is True:
            primary_count += 1
        stop_ids = require_list(route, "stop_ids", where, errors)
        leg_ids = require_list(route, "leg_ids", where, errors)
        if len(stop_ids) < 1:
            errors.append(f"{where}.stop_ids must contain at least one stop")
        if len(leg_ids) != max(0, len(stop_ids) - 1):
            errors.append(f"{where}.leg_ids must contain exactly len(stop_ids)-1 entries")
        for stop_id in stop_ids:
            if stop_id not in stop_by_id:
                errors.append(f"{where}.stop_ids references unknown stop {stop_id}")
        for pos, leg_id in enumerate(leg_ids):
            used_leg_ids.add(leg_id)
            leg = leg_by_id.get(leg_id)
            if not leg:
                errors.append(f"{where}.leg_ids references unknown leg {leg_id}")
                continue
            if pos + 1 < len(stop_ids) and (leg.get("from"), leg.get("to")) != (stop_ids[pos], stop_ids[pos + 1]):
                errors.append(f"{where} leg {leg_id} does not connect consecutive stops {stop_ids[pos]} -> {stop_ids[pos + 1]}")
    if primary_count != 1:
        errors.append("routes must contain exactly one primary route")
    unused_legs = sorted(set(leg_by_id) - used_leg_ids)
    if unused_legs:
        warnings.append(f"legs not used by any route: {', '.join(unused_legs)}")

    timeline_stop_ids: set[str] = set()
    for index, item in enumerate(timeline):
        if not isinstance(item, dict):
            errors.append(f"timeline[{index}] must be an object")
            continue
        stop_id = require_text(item, "stop_id", f"timeline[{index}]", errors)
        if stop_id not in stop_by_id:
            errors.append(f"timeline[{index}].stop_id references unknown stop {stop_id}")
        else:
            timeline_stop_ids.add(stop_id)
        require_text(item, "label", f"timeline[{index}]", errors)
    missing_timeline = sorted(set(core_ids) - timeline_stop_ids)
    if missing_timeline:
        errors.append(f"core stops missing from timeline: {', '.join(missing_timeline)}")

    if not fallbacks:
        errors.append("at least one fallback is required")
    for index, fallback in enumerate(fallbacks):
        if not isinstance(fallback, dict):
            errors.append(f"fallbacks[{index}] must be an object")
            continue
        require_text(fallback, "trigger", f"fallbacks[{index}]", errors)
        require_text(fallback, "action", f"fallbacks[{index}]", errors)

    html_coverage: dict[str, Any] | None = None
    if html_path is not None:
        try:
            parser = CoverageParser()
            parser.feed(html_path.read_text(encoding="utf-8"))
            missing_stops = sorted(set(core_ids) - parser.stop_ids)
            missing_media = sorted(set(media_by_id) - parser.media_ids)
            if missing_stops:
                errors.append(f"HTML missing core data-stop-id values: {', '.join(missing_stops)}")
            if missing_media:
                errors.append(f"HTML missing data-media-id values: {', '.join(missing_media)}")
            html_coverage = {
                "core_stops_expected": len(core_ids),
                "core_stops_rendered": len(set(core_ids) & parser.stop_ids),
                "media_expected": len(media_by_id),
                "media_rendered": len(set(media_by_id) & parser.media_ids),
            }
        except FileNotFoundError:
            errors.append(f"HTML file not found: {html_path}")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "detail": detail,
        "counts": {
            "stops": len(stop_by_id),
            "core_stops": len(core_ids),
            "legs": len(leg_by_id),
            "routes": len(routes),
            "media": len(media_by_id),
            "sources": len(source_by_id),
        },
        "html_coverage": html_coverage,
        "limits": "Structure and coverage only; facts, licenses, safety and browser layout require separate verification.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trip_data", type=Path)
    parser.add_argument("--html", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        data = load_json(args.trip_data)
        result = validate(data, args.html)
    except ValueError as exc:
        result = {"ok": False, "errors": [str(exc)], "warnings": []}
    output = json.dumps(result, ensure_ascii=False, indent=2)
    print(output)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output + "\n", encoding="utf-8")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())

