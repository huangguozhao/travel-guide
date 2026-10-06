#!/usr/bin/env python3
"""Embed permitted local raster images and audit a shareable single HTML file.

No network access or third-party packages. The audit is structural, not evidence
verification, JavaScript execution, browser rendering, or a security audit.
"""
import argparse
import base64
import binascii
import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

ASSET = re.compile(r"\{\{asset:([^{}]+)\}\}")
MIMES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".gif": "image/gif", ".webp": "image/webp"}


def signature_ok(mime, raw):
    if mime == "image/png":
        return raw.startswith(b"\x89PNG\r\n\x1a\n")
    if mime == "image/jpeg":
        return raw.startswith(b"\xff\xd8\xff")
    if mime == "image/gif":
        return raw.startswith((b"GIF87a", b"GIF89a"))
    if mime == "image/webp":
        return raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"
    return False


def bundle(text, root):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Asset root must be a directory")
    cache = {}

    def replace(match):
        relative = Path(match.group(1).strip())
        if relative.is_absolute():
            raise ValueError("Asset references must be relative to asset root")
        target = (root / relative).resolve(strict=True)
        if not target.is_relative_to(root):
            raise ValueError("Asset reference escapes the permitted root")
        if not target.is_file() or target.suffix.lower() not in MIMES:
            raise ValueError("Only PNG, JPEG, GIF and WebP files can be embedded")
        if target not in cache:
            raw = target.read_bytes()
            mime = MIMES[target.suffix.lower()]
            if not signature_ok(mime, raw):
                raise ValueError("Image signature does not match extension: " + target.name)
            cache[target] = "data:" + mime + ";base64," + base64.b64encode(raw).decode("ascii")
        return cache[target]

    output = ASSET.sub(replace, text)
    if "{{asset:" in output:
        raise ValueError("An asset placeholder is malformed or unresolved")
    return output, len(cache)


class Audit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.errors, self.warnings = [], []
        self.ids, self.fragments = [], []
        self.images = self.embedded_images = self.h1 = 0
        self.doctype = self.title = self.viewport = False
        self.styles, self.css = [], []

    def resource(self, url, where):
        if url and not url.startswith(("data:", "#")):
            # Relative and absolute file paths also prevent portable single-file use.
            self.errors.append("Non-embedded rendering resource: " + where)

    def image_data(self, src):
        if not src.startswith("data:image/"):
            return
        self.embedded_images += 1
        if ";base64," not in src:
            if not src.startswith("data:image/svg+xml"):
                self.warnings.append("Image data URI is not base64; verify in browser")
            return
        head, encoded = src.split(",", 1)
        mime = head.split(";", 1)[0][5:]
        try:
            raw = base64.b64decode(encoded, validate=True)
            if not raw or (mime in MIMES.values() and not signature_ok(mime, raw)):
                raise ValueError("Invalid signature")
        except (binascii.Error, ValueError):
            self.errors.append("Damaged embedded image data or MIME/signature mismatch")

    def handle_decl(self, decl):
        if decl.lower() == "doctype html":
            self.doctype = True

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.append(a["id"])
        if tag == "h1":
            self.h1 += 1
        if tag == "title":
            self.title = True
        if tag == "meta" and a.get("name", "").lower() == "viewport":
            self.viewport = "width=device-width" in a.get("content", "").replace(" ", "")
        if tag == "a" and a.get("href", "").startswith("#") and a["href"] != "#":
            self.fragments.append(unquote(a["href"][1:]))
        if tag == "style":
            self.styles.append(True)
        if a.get("style"):
            self.css.append(a["style"])
        if tag == "img":
            self.images += 1
            if "alt" not in a:
                self.warnings.append("Image lacks alt text")
            if not a.get("src") and not a.get("srcset") and "data-dynamic-image" not in a:
                self.warnings.append("Image has no initial source; verify dynamic loading")
            self.image_data(a.get("src", ""))
        if tag in {"img", "script", "iframe", "audio", "video", "source", "track", "embed"}:
            self.resource(a.get("src", ""), tag + " src")
        if tag == "video":
            self.resource(a.get("poster", ""), "video poster")
        if tag == "object":
            self.resource(a.get("data", ""), "object data")
        if tag == "image":
            self.resource(a.get("href", a.get("xlink:href", "")), "SVG image")
        if tag == "link":
            rel = set(a.get("rel", "").lower().split())
            if rel.intersection({"stylesheet", "icon", "preload", "modulepreload"}):
                self.resource(a.get("href", ""), "link rendering resource")
        if tag in {"img", "source"} and a.get("srcset"):
            # Embedded data URIs contain commas; browser validation still required.
            if not a["srcset"].lstrip().startswith("data:"):
                self.errors.append("Non-embedded srcset; inline it or remove it")
            else:
                self.warnings.append("Embedded srcset requires browser verification")

    def handle_endtag(self, tag):
        if tag == "style" and self.styles:
            self.styles.pop()

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        if self.styles:
            self.css.append(data)

    def finish(self, text):
        self.close()
        duplicates = [k for k, count in Counter(self.ids).items() if count > 1]
        for duplicate in duplicates:
            self.errors.append("Duplicate id: " + duplicate)
        for missing in sorted(set(self.fragments) - set(self.ids)):
            self.errors.append("Missing internal link target: " + missing)
        if not self.viewport:
            self.errors.append("Missing width=device-width viewport declaration")
        if not self.title:
            self.errors.append("Missing document title")
        if not self.doctype:
            self.warnings.append("Missing HTML5 doctype")
        if self.h1 != 1:
            self.warnings.append("Expected one primary heading; found " + str(self.h1))
        if "{{asset:" in text:
            self.errors.append("Unresolved asset placeholder")
        # CSS only, not URL strings in navigation links, citations, or JS examples.
        for css in self.css:
            for match in re.finditer(r"url\(\s*(['\"]?)(.*?)\1\s*\)", css, re.I | re.S):
                self.resource(match.group(2).strip(), "CSS url()")
            if re.search(r"@import\s+['\"]", css, re.I):
                self.errors.append("External CSS @import")
        return {"ok": not self.errors, "errors": sorted(set(self.errors)),
                "warnings": sorted(set(self.warnings)), "images": self.images,
                "embedded_images": self.embedded_images,
                "limits": "Static structure only; facts, photo-subject accuracy, JS, layout and dynamic requests need separate verification."}


def audit_text(text):
    parser = Audit()
    parser.feed(text)
    return parser.finish(text)


def write_new(path, text, overwrite=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w" if overwrite else "x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pack = commands.add_parser("pack", help="Inline {{asset:relative/path.jpg}} images")
    pack.add_argument("source", type=Path)
    pack.add_argument("--out", type=Path, required=True)
    pack.add_argument("--asset-root", type=Path)
    pack.add_argument("--overwrite", action="store_true")
    check = commands.add_parser("audit", help="Check single-file HTML structure")
    check.add_argument("source", type=Path)
    check.add_argument("--report", type=Path)
    check.add_argument("--overwrite", action="store_true", help="Replace a previous QA report")
    args = parser.parse_args()
    try:
        text = args.source.read_text(encoding="utf-8-sig")
        if args.command == "pack":
            if args.out.resolve() == args.source.resolve():
                raise ValueError("Output must differ from source")
            text, count = bundle(text, args.asset_root or args.source.parent)
            report = audit_text(text)
            report["unique_assets_embedded"] = count
            if report["ok"]:
                write_new(args.out, text, args.overwrite)
                report["output"] = str(args.out.resolve())
        else:
            report = audit_text(text)
            if args.report:
                if args.report.resolve() == args.source.resolve():
                    raise ValueError("Report must differ from source")
                write_new(args.report, json.dumps(report, ensure_ascii=False, indent=2), args.overwrite)
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 0 if report["ok"] else 1
    except (OSError, ValueError, UnicodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
