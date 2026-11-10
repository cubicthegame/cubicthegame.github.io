"""Regression checks for folder discovery and generated press kit links."""
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit
from html.parser import HTMLParser
import xml.etree.ElementTree as ET

from build import DIST, list_presskit, main


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []
        self.downloads = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for attr in ("src", "href"):
            if attrs.get(attr):
                self.paths.append(attrs[attr])
        if tag == "a" and "download" in attrs:
            self.downloads.append(attrs["href"])


class PresskitTests(unittest.TestCase):
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
        main()
        parser = Links()
        parser.feed((DIST / "presskit.html").read_text(encoding="utf-8"))
        for path in parser.paths:
            if not urlsplit(path).scheme and path != "#":
                self.assertTrue((DIST / unquote(path)).is_file(), path)
        sections = list_presskit()
        expected = {d["path"].lstrip("/") for s in sections for i in s["items"] for d in i["downloads"]}
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


if __name__ == "__main__":
    unittest.main()
