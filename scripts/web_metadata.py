"""Brand Flet's static HTML for link previews, without changing its bootstrap.

Run after ``flet publish``; this uses only Python's standard library. Images
are pre-rendered in web_preview, so publishing does not need Pillow.
"""
from __future__ import annotations

import argparse
import hashlib
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urljoin, urlsplit, urlunsplit


APP_NAME = "BLD Letter Memo"
TITLE = "BLD Letter Memo | Blindfold Cube Training"
DESCRIPTION = (
    "Train blindfolded 3×3 solving with your letter scheme, letter pairs, "
    "Progressive Memo, a blind timer, and 3-style algorithms."
)
THEME_COLOR = "#111917"
CARD_NAME = "share-card-v1.png"
CARD_ALT = "BLD Letter Memo — build your memo, train your recall. A blindfold cube training workspace."
DEFAULT_SITE_URL = "https://thomassjarner.github.io/bld-letter-memo/"
START = "BLD SHARE METADATA START"
END = "BLD SHARE METADATA END"


def normalize_site_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if (parsed.scheme not in {"https", "http"} or not parsed.netloc
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("site-url must be an absolute HTTP(S) URL without credentials, query or fragment")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/") + "/", "", ""))


class _ManagedHead(HTMLParser):
    """Locate just managed head tags; never rewrite scripts or the app body."""

    def __init__(self, source: str):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.lines = [0]
        self.lines.extend(match.end() for match in re.finditer("\n", source))
        self.in_head = False
        self.head_end = None
        self.title_start = None
        self.block_start = None
        self.spans = []
        self.feed(source)
        self.close()

    def source_offset(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag, attrs):
        if tag == "head":
            self.in_head = True
        if not self.in_head:
            return
        attrs = {key.lower(): (value or "") for key, value in attrs}
        managed = False
        if tag == "title":
            self.title_start = self.source_offset()
        elif tag == "meta":
            name = attrs.get("name", "").lower()
            prop = attrs.get("property", "").lower()
            managed = (name in {"description", "application-name", "apple-mobile-web-app-title", "theme-color"}
                       or name.startswith(("twitter:", "og:"))
                       or prop.startswith(("og:", "twitter:")))
        elif tag == "link":
            rel = set(attrs.get("rel", "").lower().split())
            managed = bool(rel & {"canonical", "icon", "apple-touch-icon"})
        if managed:
            start = self.source_offset()
            self.spans.append((start, start + len(self.get_starttag_text())))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "title" and self.in_head and self.title_start is not None:
            self.spans.append((self.title_start, self.source.index(">", self.source_offset()) + 1))
            self.title_start = None
        elif tag == "head":
            self.head_end = self.source_offset()
            self.in_head = False

    def handle_comment(self, data):
        if not self.in_head:
            return
        if data.strip() == START:
            self.block_start = self.source_offset()
        elif data.strip() == END and self.block_start is not None:
            end = self.source.index("-->", self.source_offset()) + 3
            if self.source[end:end + 1] == "\n":
                end += 1
            self.spans.append((self.block_start, end))
            self.block_start = None


def patch_html(source: str, site_url: str) -> str:
    site_url = normalize_site_url(site_url)
    parser = _ManagedHead(source)
    if parser.head_end is None:
        raise ValueError("Published index.html must have a complete <head> section")
    tags = [f"<!-- {START} -->", f"<title>{escape(TITLE)}</title>"]

    def meta(key, value, attribute="name"):
        tags.append(f'<meta {attribute}="{escape(key, quote=True)}" content="{escape(value, quote=True)}">')

    meta("description", DESCRIPTION)
    meta("application-name", APP_NAME)
    meta("apple-mobile-web-app-title", "BLD Memo")
    meta("theme-color", THEME_COLOR)
    tags.extend([
        f'<link rel="canonical" href="{escape(site_url, quote=True)}">',
        '<link rel="icon" type="image/png" href="favicon.png">',
        '<link rel="apple-touch-icon" href="icons/bld-memo-192.png">',
    ])
    for key, value in {
        "og:type": "website", "og:site_name": APP_NAME,
        "og:title": TITLE, "og:description": DESCRIPTION, "og:url": site_url,
        "og:image": urljoin(site_url, CARD_NAME), "og:image:type": "image/png",
        "og:image:width": "1200", "og:image:height": "630", "og:image:alt": CARD_ALT,
    }.items():
        meta(key, value, "property")
    for key, value in {
        "twitter:card": "summary_large_image", "twitter:title": TITLE,
        "twitter:description": DESCRIPTION, "twitter:image": urljoin(site_url, CARD_NAME),
        "twitter:image:alt": CARD_ALT,
    }.items():
        meta(key, value)
    tags.append(f"<!-- {END} -->\n")
    block = "\n".join(tags)

    # Spans can overlap when replacing our own previous metadata block.
    parts, cursor = [], 0
    for start, end in sorted(parser.spans):
        if start >= cursor:
            parts.append(source[cursor:start])
        cursor = max(cursor, end)
    parts.extend([source[cursor:parser.head_end], block, source[parser.head_end:]])
    return "".join(parts)


def patch_manifest(source: str) -> str:
    manifest = json.loads(source)
    manifest.update({
        "name": APP_NAME, "short_name": "BLD Memo", "description": DESCRIPTION,
        "background_color": THEME_COLOR, "theme_color": THEME_COLOR,
        "icons": [
            {"src": f"icons/bld-memo-{size}.png", "sizes": f"{size}x{size}",
             "type": "image/png", "purpose": "any maskable"}
            for size in (192, 512)
        ],
    })
    return json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"


def refresh_service_worker(output: Path) -> None:
    """Keep Flutter's existing cache map consistent with changed file bytes."""
    path = output / "flutter_service_worker.js"
    if not path.exists():
        return
    source = path.read_text(encoding="utf-8")
    match = re.search(r"\bconst\s+RESOURCES\s*=\s*", source)
    if not match:
        return  # Some Flet versions ship a cleanup-only service worker.
    resources, count = json.JSONDecoder().raw_decode(source[match.end():])
    if not isinstance(resources, dict):
        raise ValueError("Unexpected Flutter service-worker resources map")
    for name, digest in resources.items():
        target = output / ("index.html" if name == "/" else name)
        if (target.resolve().is_relative_to(output.resolve()) and target.is_file()
                and isinstance(digest, str) and re.fullmatch(r"[a-fA-F0-9]{32}", digest)):
            resources[name] = hashlib.md5(target.read_bytes()).hexdigest()
    path.write_text(source[:match.end()] + json.dumps(resources, separators=(",", ":"))
                    + source[match.end() + count:], encoding="utf-8")


def prepare_preview(output: Path, site_url: str = DEFAULT_SITE_URL) -> None:
    output = Path(output)
    site_url = normalize_site_url(site_url)
    assets = Path(__file__).resolve().parents[1] / "web_preview"
    index = output / "index.html"
    manifest = output / "manifest.json"
    # Validate inputs before touching the published build.
    html = patch_html(index.read_text(encoding="utf-8"), site_url)
    pwa = patch_manifest(manifest.read_text(encoding="utf-8"))
    copies = {
        CARD_NAME: output / CARD_NAME,
        "favicon.png": output / "favicon.png",
        "app-icon-192.png": output / "icons/bld-memo-192.png",
        "app-icon-512.png": output / "icons/bld-memo-512.png",
    }
    for name in copies:
        if not (assets / name).is_file():
            raise FileNotFoundError(f"Missing bundled preview image: {name}")
    for name, target in copies.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(assets / name, target)
    index.write_text(html, encoding="utf-8")
    manifest.write_text(pwa, encoding="utf-8")
    refresh_service_worker(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("dist"))
    parser.add_argument("--site-url", default=DEFAULT_SITE_URL)
    args = parser.parse_args()
    prepare_preview(args.output, args.site_url)
    print(f"Branded web preview prepared in {args.output}")


if __name__ == "__main__":
    main()
