"""Regression checks for folder discovery and generated press kit links."""
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit
from html.parser import HTMLParser
import xml.etree.ElementTree as ET
import hashlib
import os
import subprocess
from datetime import date
from unittest.mock import patch

from PIL import Image, ImageChops
import build
from media import Media

from build import ASSETS, DIST, list_presskit, main, make_url, source_lastmod


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []
        self.downloads = []
        self.images = []
        self.metadata = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for attr in ("src", "href"):
            if attrs.get(attr):
                self.paths.append(attrs[attr])
        if tag == "a" and "download" in attrs:
            self.downloads.append(attrs["href"])
        if tag == "img":
            self.images.append(attrs)
        if tag == "meta":
            self.metadata[attrs.get("property", attrs.get("name"))] = attrs.get("content")
        for key in ("poster", "data-src"):
            if attrs.get(key):
                self.paths.append(attrs[key])
        if attrs.get("srcset"):
            self.paths.extend(candidate.strip().split()[0] for candidate in attrs["srcset"].split(","))


class PresskitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        main()

    def test_discover_added_items_and_optional_formats(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            item = root / "new-category" / "new-art"
            item.mkdir(parents=True)
            (item / "new-art-1x.png").write_bytes(b"small")
            (item / "new-art-2x.png").write_bytes(b"larger image")
            (item / "source file.ai").write_bytes(b"source")
            (item / "notes.txt").write_text("ignored")
            section, = list_presskit(root)
            art, = section["items"]
            self.assertEqual(section["title"], "New Category")
            self.assertTrue(art["preview"].endswith("new-art-1x.png"))
            self.assertEqual({d["label"] for d in art["downloads"]},
                             {"PNG 1x", "PNG 2x", "Illustrator (.ai)"})
            self.assertTrue(any("source%20file.ai" in d["path"] for d in art["downloads"]))
            (item / "new-art-1x.png").unlink()
            (item / "new-art-2x.png").unlink()
            (item / "new-art.svg").write_text("<svg/>")
            self.assertTrue(list_presskit(root)[0]["items"][0]["preview"].endswith(".svg"))
            (item / "new-art.svg").unlink()
            with self.assertRaisesRegex(ValueError, "needs a preview image"):
                list_presskit(root)

    def test_build_links_and_image_sitemap(self):
        parser = Links()
        parser.feed((DIST / "presskit.html").read_text(encoding="utf-8"))
        for path in parser.paths:
            if not urlsplit(path).scheme and path != "#":
                target = DIST / unquote(path).lstrip("/")
                if path.endswith("/"):
                    target /= "index.html"
                self.assertTrue(target.is_file(), path)
        sections = list_presskit()
        expected = {d["path"] for s in sections for i in s["items"] for d in i["downloads"]}
        self.assertTrue(expected.issubset(set(parser.downloads)))
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9",
              "i": "http://www.google.com/schemas/sitemap-image/1.1"}
        tree = ET.parse(DIST / "sitemap.xml")
        for image in tree.findall(".//i:loc", ns):
            self.assertTrue((DIST / unquote(urlsplit(image.text).path.lstrip("/"))).is_file(), image.text)
            self.assertNotIn(".webm", image.text)
        press = next(p for p in tree.findall("s:url", ns)
                     if p.find("s:loc", ns).text.endswith("/presskit.html"))
        image_paths = {urlsplit(n.text).path for n in press.findall(".//i:loc", ns)}
        for section in sections:
            for item in section["items"]:
                self.assertTrue(set(item["images"]).issubset(image_paths))

    def test_canonical_links_and_all_rendered_resources(self):
        for base in ("", "../", "../../"):
            url = make_url(base)
            self.assertEqual(url("/"), "/")
            self.assertEqual(url("/news/"), "/news/")
            self.assertEqual(url("/news/test/"), "/news/test/")
            self.assertEqual(url("#trailer"), "#trailer")
        self.assertEqual(make_url("https://example.com/")("/news/"), "https://example.com/news/")
        for page in DIST.rglob("*.html"):
            parser = Links()
            parser.feed(page.read_text(encoding="utf-8"))
            for path in parser.paths:
                if urlsplit(path).scheme or path.startswith(("#", "//")):
                    continue
                self.assertNotIn("index.html", path, (page, path))
                target = DIST / unquote(urlsplit(path).path).lstrip("/")
                if path.endswith("/"):
                    target /= "index.html"
                self.assertTrue(target.is_file(), (page, path))
            for attrs in parser.images:
                if urlsplit(attrs["src"]).scheme:
                    continue
                self.assertIn("width", attrs)
                self.assertIn("height", attrs)
            sharing = urlsplit(parser.metadata["og:image"])
            with Image.open(DIST / unquote(sharing.path).lstrip("/")) as image:
                self.assertEqual(image.size, (int(parser.metadata["og:image:width"]),
                                              int(parser.metadata["og:image:height"])))

    def test_modern_sitemap_and_robots(self):
        sitemap = (DIST / "sitemap.xml").read_text(encoding="utf-8")
        for deprecated in ("image:caption", "priority", "changefreq"):
            self.assertNotIn(deprecated, sitemap)
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for page in ET.fromstring(sitemap).findall("s:url", ns):
            self.assertNotIn("index.html", page.find("s:loc", ns).text)
            modified = page.find("s:lastmod", ns)
            if modified is not None:
                self.assertLessEqual(date.fromisoformat(modified.text), date.today())
            locations = [node.text for node in page.iter() if node.tag.endswith("loc")]
            self.assertEqual(len(locations), len(set(locations)))
        self.assertIn("Sitemap: https://www.cubicthegame.com/sitemap.xml", (DIST / "robots.txt").read_text())

    def test_original_assets_are_unchanged(self):
        for source in ASSETS.rglob("*"):
            if source.is_file():
                copied = DIST / "assets" / source.relative_to(ASSETS)
                self.assertEqual(hashlib.sha256(source.read_bytes()).digest(),
                                 hashlib.sha256(copied.read_bytes()).digest(), source)

    def test_press_previews_use_small_images_and_keep_downloads(self):
        parser = Links()
        html = (DIST / "presskit.html").read_text(encoding="utf-8")
        parser.feed(html)
        self.assertNotIn('id="screenshots"', html)
        previews = [image for image in parser.images if "/generated/presskit/" in image["src"]]
        self.assertEqual(len(previews), sum(len(section["items"]) for section in list_presskit()))
        for attrs in previews:
            self.assertIn("srcset", attrs)
            self.assertNotIn(attrs["src"], parser.downloads)
            self.assertLess((DIST / attrs["src"].lstrip("/")).stat().st_size, 150_000)


class MediaTests(unittest.TestCase):
    def test_lossless_previews_preserve_alpha_and_original_files(self):
        with tempfile.TemporaryDirectory() as temp:
            assets = Path(temp) / "assets"
            assets.mkdir()
            source = assets / "transparent logo.png"
            original = Image.new("RGBA", (800, 400), (125, 60, 200, 0))
            original.paste((30, 80, 140, 255), (200, 100, 600, 300))
            original.save(source)
            before = source.read_bytes()
            output = Path(temp) / "output"
            media = Media(assets, output)
            result = media.image("/assets/transparent%20logo.png", (260, 520, 1600))
            self.assertEqual([c["width"] for c in result["candidates"]], [260, 520, 800])
            for candidate in result["candidates"]:
                file = output / unquote(candidate["path"].removeprefix("/assets/"))
                with Image.open(file) as actual:
                    expected = original.resize((candidate["width"], candidate["height"]), Image.Resampling.LANCZOS)
                    self.assertIsNone(ImageChops.difference(actual.getchannel("A"), expected.getchannel("A")).getbbox())
                    self.assertEqual(actual.getpixel((actual.width // 2, actual.height // 2)), (30, 80, 140, 255))
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(media.image("/assets/transparent%20logo.png", (260, 520, 1600)), result)
            social = media.image("/assets/transparent%20logo.png", (260,), social=True)
            self.assertTrue(social["src"].endswith(".png"))

    def test_svg_only_item_and_external_images(self):
        with tempfile.TemporaryDirectory() as temp:
            assets = Path(temp) / "assets"
            assets.mkdir()
            (assets / "logo.svg").write_text('<svg viewBox="0 0 200 100"/>')
            media = Media(assets, Path(temp) / "output")
            svg = media.image("/assets/logo.svg")
            self.assertEqual((svg["src"], svg["width"], svg["height"]), ("/assets/logo.svg", 200, 100))
            self.assertEqual(media.image("https://example.com/image.png")["src"], "https://example.com/image.png")


class ModificationDateTests(unittest.TestCase):
    def test_rebuild_dates_follow_relevant_source_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            def git(*args, env=None):
                return subprocess.run(["git", "-c", f"safe.directory={root.as_posix()}",
                                       "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
                                      cwd=root, env=env, check=True, capture_output=True)

            git("init")
            (root / "content.md").write_text("original")
            git("add", "content.md")
            env = dict(os.environ, GIT_AUTHOR_DATE="2020-01-02T12:00:00+00:00", GIT_COMMITTER_DATE="2020-01-02T12:00:00+00:00")
            git("commit", "-m", "Content", env=env)
            (root / "unrelated.txt").write_text("unrelated")
            git("add", "unrelated.txt")
            env.update(GIT_AUTHOR_DATE="2022-01-02T12:00:00+00:00", GIT_COMMITTER_DATE="2022-01-02T12:00:00+00:00")
            git("commit", "-m", "Unrelated", env=env)
            with patch.object(build, "ROOT", root):
                source_lastmod.cache_clear()
                self.assertEqual(source_lastmod("content.md"), "2020-01-02")
                (root / "content.md").write_text("updated")
                source_lastmod.cache_clear()
                self.assertEqual(source_lastmod("content.md"), date.today().isoformat())
            source_lastmod.cache_clear()


if __name__ == "__main__":
    unittest.main()
