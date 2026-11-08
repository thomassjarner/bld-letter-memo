"""Link crawlers read the published head without running the Python app."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import struct

import pytest

from scripts.web_metadata import (
    APP_NAME, CARD_NAME, DESCRIPTION, TITLE, normalize_site_url, patch_html,
    prepare_preview, refresh_service_worker,
)


BOOTSTRAP = '''<script>
var flet = {baseURL: "/test-repo/", pyodide: true};
const example = '<meta name="description" content="keep script text">';
</script>
<script src="flutter_bootstrap.js" async></script>'''
TEMPLATE = '''<!DOCTYPE html>
<html><head>
<base href="/test-repo/">
<meta charset="UTF-8">
<meta name="description" content="Flet application.">
<meta name="apple-mobile-web-app-title" content="Flet">
<link rel="icon" type="image/png" href="favicon.png" />
<link rel="apple-touch-icon" href="icons/apple-touch-icon-192.png">
<link rel="manifest" href="manifest.json">
<TITLE>test-repo</TITLE>
''' + BOOTSTRAP + '''
</head><body><div id="app">Loading…</div></body></html>'''
SITE_URL = "https://example.github.io/test-repo/"


class Head(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.metas, self.links, self.titles = [], [], []
        self.in_title = False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == "meta":
            self.metas.append(dict(attrs))
        elif tag == "link":
            self.links.append(dict(attrs))
        elif tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.titles.append(data)

    def meta(self, name):
        values = [tag["content"] for tag in self.metas if tag.get("name", tag.get("property")) == name]
        assert len(values) == 1, (name, values)
        return values[0]


def build_fixture(path):
    path.mkdir()
    (path / "index.html").write_text(TEMPLATE, encoding="utf-8")
    (path / "manifest.json").write_text(json.dumps({
        "name": "Flet", "short_name": "Flet", "start_url": ".",
        "display": "standalone", "orientation": "natural", "custom": True,
    }))
    return path


def test_published_preview_has_single_branded_metadata_and_keeps_runtime():
    source = TEMPLATE.replace("</TITLE>", '</TITLE><meta property="og:title" content="old">'
                              '<meta name="twitter:card" content="summary">')
    patched = patch_html(source, SITE_URL)
    head = Head(patched)
    assert head.titles == [TITLE]
    assert head.meta("description") == DESCRIPTION
    assert head.meta("og:title") == TITLE
    assert head.meta("og:site_name") == APP_NAME
    assert head.meta("og:type") == "website"
    assert head.meta("og:url") == SITE_URL
    assert head.meta("og:image") == SITE_URL + CARD_NAME
    assert (head.meta("og:image:width"), head.meta("og:image:height")) == ("1200", "630")
    assert head.meta("og:image:alt")
    assert head.meta("twitter:card") == "summary_large_image"
    assert head.meta("twitter:image") == SITE_URL + CARD_NAME
    assert [tag["href"] for tag in head.links if tag["rel"] == "canonical"] == [SITE_URL]
    assert BOOTSTRAP in patched
    assert '<base href="/test-repo/">' in patched
    assert '<link rel="manifest" href="manifest.json">' in patched
    assert patched.endswith('<body><div id="app">Loading…</div></body></html>')
    assert patch_html(patched, SITE_URL) == patched


def test_republishing_with_renamed_repo_replaces_all_old_share_urls():
    first = patch_html(TEMPLATE, SITE_URL)
    second = patch_html(first, "https://other.github.io/renamed")
    head = Head(second)
    assert head.meta("og:url") == "https://other.github.io/renamed/"
    assert head.meta("og:image") == "https://other.github.io/renamed/" + CARD_NAME
    assert SITE_URL not in second


@pytest.mark.parametrize("url", ["relative/path", "file:///app", "https://host/app?q=1",
                                  "https://host/app#memo", "https://user:secret@host/"])
def test_invalid_share_urls_are_rejected(url):
    with pytest.raises(ValueError, match="absolute HTTP"):
        normalize_site_url(url)


def test_build_copies_real_sized_assets_and_preserves_pwa_navigation(tmp_path):
    output = build_fixture(tmp_path / "dist")
    worker = "'use strict';\nself.addEventListener('activate', () => self.skipWaiting());\n"
    (output / "flutter_service_worker.js").write_text(worker)
    prepare_preview(output, SITE_URL)
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["name"] == APP_NAME and manifest["short_name"] == "BLD Memo"
    assert manifest["start_url"] == "." and manifest["display"] == "standalone"
    assert manifest["orientation"] == "natural" and manifest["custom"] is True
    assert (output / "flutter_service_worker.js").read_text() == worker
    for path, expected in [(output / CARD_NAME, (1200, 630)),
                           (output / "favicon.png", (64, 64)),
                           *[(output / icon["src"], (size, size))
                             for icon, size in zip(manifest["icons"], (192, 512))]]:
        data = path.read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack(">II", data[16:24]) == expected
    first = {str(path.relative_to(output)): path.read_bytes() for path in output.rglob("*") if path.is_file()}
    prepare_preview(output, SITE_URL)
    assert first == {str(path.relative_to(output)): path.read_bytes() for path in output.rglob("*") if path.is_file()}


def test_existing_flutter_cache_hashes_match_postprocessed_files(tmp_path):
    output = build_fixture(tmp_path / "dist")
    resources = {"index.html": "0" * 32, "/": "0" * 32, "manifest.json": "0" * 32,
                 "favicon.png": "0" * 32, "not-in-build.js": "1" * 32}
    suffix = "\nself.addEventListener('fetch', () => {});"
    worker = output / "flutter_service_worker.js"
    worker.write_text("const RESOURCES = " + json.dumps(resources) + ";" + suffix)
    prepare_preview(output, SITE_URL)
    source = worker.read_text()
    actual, _ = json.JSONDecoder().raw_decode(source[len("const RESOURCES = "):])
    for name in ("index.html", "/", "manifest.json", "favicon.png"):
        target = output / ("index.html" if name == "/" else name)
        assert actual[name] == hashlib.md5(target.read_bytes()).hexdigest()
    assert actual["not-in-build.js"] == "1" * 32
    assert source.endswith(suffix)
    refresh_service_worker(output)
    assert worker.read_text() == source


def test_missing_html_or_broken_head_fails_before_modifying_build(tmp_path):
    with pytest.raises(FileNotFoundError):
        prepare_preview(tmp_path, SITE_URL)
    output = build_fixture(tmp_path / "dist")
    path = output / "index.html"
    path.write_text("<html><body>No head</body></html>")
    before = (output / "manifest.json").read_bytes()
    with pytest.raises(ValueError, match="complete <head>"):
        prepare_preview(output, SITE_URL)
    assert (output / "manifest.json").read_bytes() == before
    assert not (output / CARD_NAME).exists()


def test_deployment_brands_published_html_before_upload():
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/deploy.yml").read_text()
    assert workflow.index("flet publish main.py") < workflow.index("python scripts/web_metadata.py") < workflow.index("actions/upload-pages-artifact")
    assert '--site-url "https://${{ github.repository_owner }}.github.io/${{ github.event.repository.name }}/"' in workflow
