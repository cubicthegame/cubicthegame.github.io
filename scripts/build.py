#!/usr/bin/env python3
"""
Build script for the Cubic website.

What it does:
  1. Reads content/config.yaml for site-wide settings.
  2. Reads every content/posts/*.md file (YAML frontmatter + markdown body),
     turns each into a news post page at /news/<slug>/index.html, and
     builds the /news/ index page + the "latest 3" list used on the homepage.
  3. Renders index.html, presskit.html, terms.html, privacy.html.
  4. Generates responsive display images and copies original assets unchanged.
  5. Generates sitemap.xml and robots.txt.

Run it with:  python3 scripts/build.py
Output goes to ./dist  (this folder is what gets deployed to GitHub Pages -
see .github/workflows/deploy.yml).

To add a new blog post: drop a new markdown file into content/posts/,
named e.g. 2026-06-01-my-post-title.md, with frontmatter like:

    ---
    title: "My Post Title"
    date: 2026-06-01
    excerpt: "One or two sentences shown on the news list."
    cover: /assets/images/screenshots/screenshot-1.jpg
    ---

    Body in **markdown** goes here.

Push to main and the GitHub Action rebuilds and redeploys the whole site
automatically - no manual HTML editing required.
"""
import shutil
import re
from pathlib import Path
from datetime import datetime, date
import json
import hashlib
import subprocess
from functools import lru_cache
from html import unescape
from urllib.parse import quote

import yaml
import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape
from media import Media

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
TEMPLATES = ROOT / "templates"
ASSETS = ROOT / "assets"
DIST = ROOT / "dist"

SCREENSHOTS_DIR = ASSETS / "images" / "screenshots"
PRESSKIT_DIR = ASSETS / "presskit"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
DOWNLOAD_EXTENSIONS = IMAGE_EXTENSIONS | {".ai", ".pdf", ".eps", ".psd", ".zip"}


def load_config():
    with open(CONTENT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&apos;"))


def format_date(d) -> str:
    """'%B %-d, %Y' but portable - %-d is Linux/Mac-only and crashes on Windows."""
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def make_url(base: str):
    """Use canonical root-relative URLs; the 404 page uses an absolute prefix.

    Preview dist with an HTTP server rather than opening HTML via file://.
    """
    def _url(path: str) -> str:
        if path.startswith(("http://", "https://", "mailto:", "#", "//")):
            return path
        if base.startswith(("http://", "https://")):
            return base.rstrip("/") + "/" + path.lstrip("/")
        return "/" + path.lstrip("/")
    return _url


@lru_cache(maxsize=None)
def source_lastmod(*paths):
    """Use source history, not checkout mtimes or the date of every rebuild."""
    command = ["git", "-c", f"safe.directory={ROOT.as_posix()}"]
    try:
        changed = subprocess.run(command + ["status", "--porcelain", "--", *paths],
                                 cwd=ROOT, check=True, capture_output=True, text=True)
        if changed.stdout.strip():
            return date.today().isoformat()
        history = subprocess.run(command + ["log", "-1", "--format=%cs", "--", *paths],
                                 cwd=ROOT, check=True, capture_output=True, text=True)
        value = history.stdout.strip()
        return value if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) else None
    except (OSError, subprocess.CalledProcessError):
        # An exported checkout may have no Git history. Omit an unknown date.
        return None


def slugify(name: str) -> str:
    name = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", name)  # strip leading date from filename
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return name


def render_post_body(body_md):
    converter = markdown.Markdown(
        extensions=["extra", "smarty", "toc"],
        extension_configs={"toc": {"toc_depth": "2-3", "marker": ""}},
    )
    html = converter.convert(body_md)

    def entries(tokens):
        return [{"id": token["id"], "label": unescape(token["name"]),
                 "children": entries(token["children"])} for token in tokens]

    return html, entries(converter.toc_tokens)


def load_posts():
    posts = []
    for md_file in sorted(CONTENT.glob("posts/*.md")):
        raw = md_file.read_text(encoding="utf-8")
        fm_match = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.DOTALL)
        if not fm_match:
            raise ValueError(f"{md_file} is missing YAML frontmatter (--- ... ---)")
        meta = yaml.safe_load(fm_match.group(1))
        body_md = fm_match.group(2).strip()
        html, toc = render_post_body(body_md)

        d = meta["date"]
        if isinstance(d, str):
            d = datetime.strptime(d, "%Y-%m-%d").date()
        elif isinstance(d, datetime):
            d = d.date()

        slug = meta.get("slug") or slugify(md_file.stem)
        posts.append({
            "title": meta["title"],
            "date": d,
            "date_iso": d.isoformat(),
            "date_display": format_date(d) if hasattr(d, "strftime") else str(d),
            "excerpt": meta.get("excerpt", ""),
            "author": meta.get("author"),
            "cover": meta.get("cover", "/assets/images/screenshots/keyart1.png"),
            "slug": slug,
            "url": f"/news/{slug}/",
            "html": html,
            "toc": toc,
            "source": md_file.relative_to(ROOT).as_posix(),
        })
    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


def load_legal(name):
    raw = (CONTENT / "legal" / f"{name}.md").read_text(encoding="utf-8")
    return markdown.markdown(raw, extensions=["extra"])


def list_screenshots(cfg):
    files = sorted(SCREENSHOTS_DIR.glob("*.jpg")) + sorted(SCREENSHOTS_DIR.glob("*.png"))
    captions = cfg.get("screenshot_captions") or {}
    out = []
    for i, f in enumerate(files, start=1):
        out.append({
            "path": f"/assets/images/screenshots/{f.name}",
            "caption": captions.get(f.name, f"Cubic - screenshot {i}"),
        })
    return out


def list_presskit(directory=PRESSKIT_DIR):
    """Discover category/item folders; each item needs at least one preview image."""
    sections = []
    for category in sorted(directory.iterdir()):
        if not category.is_dir() or category.name.startswith("."):
            continue
        items = []
        for folder in sorted(category.iterdir()):
            if not folder.is_dir() or folder.name.startswith("."):
                continue
            files = sorted(
                (f for f in folder.iterdir() if f.is_file()
                 and f.suffix.lower() in DOWNLOAD_EXTENSIONS),
                key=lambda f: f.name.lower(),
            )
            if not files:
                continue
            images = [f for f in files if f.suffix.lower() in IMAGE_EXTENSIONS]
            if not images:
                raise ValueError(f"Press kit item {folder} needs a preview image")
            # Prefer a small raster preview over large exports or SVG source.
            preview = min(images, key=lambda f: (f.suffix.lower() == ".svg", f.stat().st_size, f.name))
            title = folder.name.replace("-", " ").replace("_", " ").capitalize()

            def asset_path(file):
                return "/assets/presskit/" + quote(file.relative_to(directory).as_posix())

            downloads = []
            for file in files:
                label = file.suffix[1:].upper()
                if label == "AI":
                    label = "Illustrator (.ai)"
                scale = re.search(r"(?:-|@)(\d+x)$", file.stem, re.IGNORECASE)
                if scale:
                    label += f" {scale.group(1).lower()}"
                downloads.append({"path": asset_path(file), "label": label})
            items.append({
                "title": title,
                "caption": f"Cubic - {title}",
                "preview": asset_path(preview),
                "images": [asset_path(f) for f in images],
                "downloads": downloads,
            })
        if items:
            sections.append({
                "id": slugify(category.name),
                "title": category.name.replace("-", " ").replace("_", " ").title(),
                "items": items,
            })
    return sections


def video_game_schema(cfg):
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "VideoGame",
        "name": cfg["site_name"],
        "description": cfg["tagline"],
        "url": cfg["site_url"],
        "image": f"{cfg['site_url']}{cfg['default_og_image']}",
        "publisher": {"@type": "Organization", "name": cfg["studio_name"]},
        "trailer": {
            "@type": "VideoObject",
            "name": f"{cfg['site_name']} - Official Trailer",
            "description": cfg["tagline"],
            "thumbnailUrl": f"{cfg['site_url']}/assets/images/trailer-poster.jpg",
            "uploadDate": cfg["trailer_upload_date"],
            "embedUrl": f"https://www.youtube-nocookie.com/embed/{cfg['trailer_youtube_id']}",
        },
    }, ensure_ascii=False)


def article_schema(cfg, post):
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": post["title"],
        "description": post["excerpt"],
        "datePublished": post["date_iso"],
        "image": f"{cfg['site_url']}{post['cover']}",
        "author": {"@type": "Person" if post.get("author") else "Organization",
                   "name": post.get("author") or cfg["studio_name"]},
        "publisher": {"@type": "Organization", "name": cfg["studio_name"]},
        "mainEntityOfPage": f"{cfg['site_url']}{post['url']}",
    }, ensure_ascii=False)


def main():
    cfg = load_config()
    posts = load_posts()
    screenshots = list_screenshots(cfg)
    presskit_sections = list_presskit()

    if DIST.exists():
        if DIST.resolve() != ROOT / "dist":
            raise ValueError("Build output must resolve to the workspace dist directory")
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    source_lastmod.cache_clear()
    media = Media(ASSETS, DIST / "assets")

    @lru_cache(maxsize=None)
    def versioned_asset(path):
        """Change the URL with the content so cached CSS/JS matches the HTML."""
        source = ROOT / path.lstrip("/")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
        relative = source.relative_to(ROOT).with_name(f"{source.stem}-{digest}{source.suffix}")
        target = DIST / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return "/" + quote(relative.as_posix())

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(disabled_extensions=("txt",)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["image"] = media.image
    env.globals["asset"] = versioned_asset

    common = dict(
        site_url=cfg["site_url"],
        site_name=cfg["site_name"],
        studio_name=cfg["studio_name"],
        contact_email=cfg["contact_email"],
        links=cfg["links"],
        trailer_youtube_id=cfg["trailer_youtube_id"],
        newsletter_endpoint=cfg.get("newsletter_endpoint") or "#",
        year=date.today().year,
    )

    def abs_url(path):
        return f"{cfg['site_url']}{path}"

    pages = []  # for sitemap: (canonical path, source modification date, images)

    def lastmod(*paths):
        return source_lastmod("templates/base.html", "templates/_media.html",
                              "scripts/build.py", "scripts/media.py", "content/config.yaml",
                              "assets/css/style.css", "assets/js/main.js", *paths)

    # ---- Homepage ----
    html = env.get_template("index.html").render(
        **common,
        url=make_url(""),
        path="/",
        body_class="page-home",
        title=f"{cfg['site_name']} - {cfg['studio_name']}",
        description=cfg["tagline"],
        og_type="website",
        og_image=cfg["default_og_image"],
        schema=video_game_schema(cfg),
        latest_posts=posts[:3],
        screenshots=screenshots,
    )
    (DIST / "index.html").write_text(html, encoding="utf-8")
    home_images = (
        [(abs_url("/assets/images/logo-color-placeholder.png"), f"{cfg['site_name']} - game logo"),
         (abs_url("/assets/images/trailer-poster.jpg"), f"{cfg['site_name']} - official trailer preview frame"),
         (abs_url("/assets/images/bg/blackbar_intro_big.png"), f"{cfg['site_name']} - intro background"),
         (abs_url("/assets/images/bg/blackbar_desert_big.png"), f"{cfg['site_name']} - desert background"),
         (abs_url("/assets/images/bg/blackbar_crystal_big.png"), f"{cfg['site_name']} - crystal background")]
        + [(abs_url(p["cover"]), p["title"]) for p in posts[:3]]
    )
    pages.append(("/", lastmod("templates/index.html", "content/posts", "assets/images", "assets/webm"), home_images))

    # ---- Press kit ----
    html = env.get_template("presskit.html").render(
        **common,
        url=make_url(""),
        path="/presskit.html",
        title=f"Press Kit - {cfg['site_name']}",
        description=f"Official {cfg['site_name']} key art, logos, and downloads for press and content creators.",
        og_type="website",
        og_image=cfg["default_og_image"],
        presskit_sections=presskit_sections,
    )
    (DIST / "presskit.html").write_text(html, encoding="utf-8")
    presskit_images = (
        [(abs_url(image), item["caption"])
         for section in presskit_sections for item in section["items"]
         for image in item["images"]]
    )
    pages.append(("/presskit.html", lastmod("templates/presskit.html", "assets/presskit", cfg["default_og_image"].lstrip("/")), presskit_images))

    # ---- Legal ----
    for name, title in [("terms", "Terms of Service"), ("privacy", "Privacy Policy")]:
        legal_date = source_lastmod(f"content/legal/{name}.md")
        html = env.get_template("legal.html").render(
            **common,
            url=make_url(""),
            path=f"/{name}.html",
            title=f"{title} - {cfg['site_name']}",
            description=f"{title} for {cfg['site_name']}, by {cfg['studio_name']}.",
            page_title=title,
            updated=format_date(date.fromisoformat(legal_date)) if legal_date else None,
            body=load_legal(name),
        )
        (DIST / f"{name}.html").write_text(html, encoding="utf-8")
        pages.append((f"/{name}.html", lastmod("templates/legal.html", f"content/legal/{name}.md"), []))

    # ---- News index ----
    (DIST / "news").mkdir(parents=True, exist_ok=True)
    html = env.get_template("news_index.html").render(
        **common,
        url=make_url("../"),
        path="/news/",
        title=f"News - {cfg['site_name']}",
        description=f"Devlogs and updates about {cfg['site_name']} from {cfg['studio_name']}.",
        og_type="website",
        posts=posts,
    )
    (DIST / "news" / "index.html").write_text(html, encoding="utf-8")
    news_images = [(abs_url(p["cover"]), p["title"]) for p in posts]
    pages.append(("/news/", lastmod("templates/news_index.html", "content/posts", "assets/images/screenshots"), news_images))

    # ---- Individual posts ----
    for post in posts:
        post_dir = DIST / "news" / post["slug"]
        post_dir.mkdir(parents=True, exist_ok=True)
        html = env.get_template("post.html").render(
            **common,
            url=make_url("../../"),
            path=post["url"],
            title=f"{post['title']} - {cfg['site_name']}",
            description=post["excerpt"],
            og_type="article",
            og_image=post["cover"],
            schema=article_schema(cfg, post),
            post=post,
        )
        (post_dir / "index.html").write_text(html, encoding="utf-8")
        pages.append((post["url"], lastmod("templates/post.html", post["source"], post["cover"].lstrip("/")),
                      [(abs_url(post["cover"]), post["title"])]))

    # ---- Copy static assets ----
    shutil.copytree(ASSETS, DIST / "assets", dirs_exist_ok=True)

    # ---- sitemap.xml (with the Google image-sitemap extension) ----
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
             '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    for path, modified, images in pages:
        lines.append("  <url>")
        lines.append(f"    <loc>{xml_escape(cfg['site_url'] + path)}</loc>")
        if modified:
            lines.append(f"    <lastmod>{modified}</lastmod>")
        for img_loc in dict.fromkeys(location for location, caption in images):
            lines.append("    <image:image>")
            lines.append(f"      <image:loc>{xml_escape(img_loc)}</image:loc>")
            lines.append("    </image:image>")
        lines.append("  </url>")
    lines.append("</urlset>")
    (DIST / "sitemap.xml").write_text("\n".join(lines), encoding="utf-8")

    # ---- robots.txt ----
    robots = f"User-agent: *\nAllow: /\nSitemap: {cfg['site_url']}/sitemap.xml\n"
    (DIST / "robots.txt").write_text(robots, encoding="utf-8")

    # ---- 404 page (GitHub Pages convention) ----
    # Uses absolute URLs (not the relative ones every other page uses) because
    # GitHub Pages can serve this file for a request at any depth/path.
    html = env.get_template("index.html").render(
        **common,
        url=make_url(cfg["site_url"] + "/"),
        path="/",
        body_class="page-home",
        title=f"{cfg['site_name']} - {cfg['studio_name']}",
        description=cfg["tagline"],
        og_type="website",
        og_image=cfg["default_og_image"],
        schema=video_game_schema(cfg),
        latest_posts=posts[:3],
        screenshots=screenshots,
    )
    (DIST / "404.html").write_text(html, encoding="utf-8")

    print(f"Built {len(pages)} pages + {len(posts)} posts into {DIST}")


if __name__ == "__main__":
    main()
