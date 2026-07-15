#!/usr/bin/env python3
"""
Build script for the Cubic website.

What it does:
  1. Reads content/config.yaml for site-wide settings.
  2. Reads every content/posts/*.md file (YAML frontmatter + markdown body),
     turns each into a news post page at /news/<slug>/index.html, and
     builds the /news/ index page + the "latest 3" list used on the homepage.
  3. Renders index.html, presskit.html, terms.html, privacy.html.
  4. Copies assets/ as-is into the output.
  5. Generates sitemap.xml and robots.txt.

Run it with:  python3 scripts/build.py
Output goes to ./dist  (this folder is what gets deployed to GitHub Pages —
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
automatically — no manual HTML editing required.
"""
import shutil
import re
from pathlib import Path
from datetime import datetime, date
import json

import yaml
import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
TEMPLATES = ROOT / "templates"
ASSETS = ROOT / "assets"
DIST = ROOT / "dist"

SCREENSHOTS_DIR = ASSETS / "images" / "screenshots"
KEYART_DIR = ASSETS / "images" / "keyart"


def load_config():
    with open(CONTENT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&apos;"))


def format_date(d) -> str:
    """'%B %-d, %Y' but portable — %-d is Linux/Mac-only and crashes on Windows."""
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def make_url(base: str):
    """
    Build a `url(path)` function for templates. `path` is written as a clean,
    root-relative site path (e.g. "/assets/css/style.css", "/news/", "/").
    `base` is either:
      - a relative prefix like "", "../", "../../"  (depends on how deep the
        current output page sits), which makes every link/asset work both
        when served by a real web server *and* when a file is opened directly
        via file:// (double-click) — no root-absolute paths anywhere, or
      - an absolute URL prefix (site_url + "/"), used only for 404.html, which
        GitHub Pages can serve from any depth so it can't rely on a relative
        prefix.
    Directory-style paths ("/", "/news/", "/news/slug/") resolve to their
    index.html so plain file:// browsing works without a server.
    """
    def _url(path: str) -> str:
        if path.startswith(("http://", "https://", "mailto:")) or path == "#":
            return path
        p = path.lstrip("/")
        if path.endswith("/") or p == "":
            p = p + "index.html"
        return base + p
    return _url


def slugify(name: str) -> str:
    name = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", name)  # strip leading date from filename
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return name


def load_posts():
    posts = []
    for md_file in sorted(CONTENT.glob("posts/*.md")):
        raw = md_file.read_text(encoding="utf-8")
        fm_match = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.DOTALL)
        if not fm_match:
            raise ValueError(f"{md_file} is missing YAML frontmatter (--- ... ---)")
        meta = yaml.safe_load(fm_match.group(1))
        body_md = fm_match.group(2).strip()
        html = markdown.markdown(body_md, extensions=["extra", "smarty"])

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
            "cover": meta.get("cover", "/assets/images/screenshots/screenshot-1.jpg"),
            "slug": slug,
            "url": f"/news/{slug}/",
            "html": html,
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
            "caption": captions.get(f.name, f"Cubic — screenshot {i}"),
        })
    return out


def list_keyart():
    items = []
    for i in range(1, 8):
        base = f"keyart-{i}"
        if not (KEYART_DIR / f"{base}.svg").exists():
            continue
        items.append({
            "index": i,
            "svg": f"/assets/images/keyart/{base}.svg",
            "png1x": f"/assets/images/keyart/{base}-1x.png",
            "png2x": f"/assets/images/keyart/{base}-2x.png",
            "ai": f"/assets/images/keyart/{base}.ai.txt",
            "caption": f"Cubic key art — piece {i}",
        })
    return items


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
            "name": f"{cfg['site_name']} — Official Trailer",
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
    keyart = list_keyart()

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(disabled_extensions=("txt",)),
        trim_blocks=True,
        lstrip_blocks=True,
    )

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

    pages = []  # for sitemap: (path, priority, changefreq, images)

    # ---- Homepage ----
    html = env.get_template("index.html").render(
        **common,
        url=make_url(""),
        path="/",
        body_class="page-home",
        title=f"{cfg['site_name']} — {cfg['studio_name']}",
        description=cfg["tagline"],
        og_type="website",
        og_image=cfg["default_og_image"],
        schema=video_game_schema(cfg),
        latest_posts=posts[:3],
        screenshots=screenshots,
    )
    (DIST / "index.html").write_text(html, encoding="utf-8")
    home_images = (
        [(abs_url("/assets/images/logo-color-placeholder.png"), f"{cfg['site_name']} — game logo"),
         (abs_url("/assets/images/trailer-poster.jpg"), f"{cfg['site_name']} — official trailer preview frame"),
         (abs_url("/assets/images/gifs/gameplay-1.gif"), f"{cfg['site_name']} gameplay — exploring an isometric land"),
         (abs_url("/assets/images/gifs/gameplay-2.gif"), f"{cfg['site_name']} gameplay — solving a puzzle")]
        + [(abs_url(s["path"]), s["caption"]) for s in screenshots]
        + [(abs_url(p["cover"]), p["title"]) for p in posts[:3]]
    )
    pages.append(("/", 1.0, "weekly", home_images))

    # ---- Press kit ----
    html = env.get_template("presskit.html").render(
        **common,
        url=make_url(""),
        path="/presskit.html",
        title=f"Press Kit — {cfg['site_name']}",
        description=f"Key art, screenshots, and facts about {cfg['site_name']} for press and content creators.",
        og_type="website",
        og_image=cfg["default_og_image"],
        keyart=keyart,
        screenshots=screenshots,
    )
    (DIST / "presskit.html").write_text(html, encoding="utf-8")
    presskit_images = (
        [(abs_url(a["png2x"]), a["caption"]) for a in keyart]
        + [(abs_url(s["path"]), s["caption"]) for s in screenshots]
    )
    pages.append(("/presskit.html", 0.6, "monthly", presskit_images))

    # ---- Legal ----
    for name, title in [("terms", "Terms of Service"), ("privacy", "Privacy Policy")]:
        html = env.get_template("legal.html").render(
            **common,
            url=make_url(""),
            path=f"/{name}.html",
            title=f"{title} — {cfg['site_name']}",
            description=f"{title} for {cfg['site_name']}, by {cfg['studio_name']}.",
            page_title=title,
            updated=format_date(date.today()),
            body=load_legal(name),
        )
        (DIST / f"{name}.html").write_text(html, encoding="utf-8")
        pages.append((f"/{name}.html", 0.2, "yearly", []))

    # ---- News index ----
    (DIST / "news").mkdir(parents=True, exist_ok=True)
    html = env.get_template("news_index.html").render(
        **common,
        url=make_url("../"),
        path="/news/",
        title=f"News — {cfg['site_name']}",
        description=f"Devlogs and updates about {cfg['site_name']} from {cfg['studio_name']}.",
        og_type="website",
        posts=posts,
    )
    (DIST / "news" / "index.html").write_text(html, encoding="utf-8")
    news_images = [(abs_url(p["cover"]), p["title"]) for p in posts]
    pages.append(("/news/", 0.8, "weekly", news_images))

    # ---- Individual posts ----
    for post in posts:
        post_dir = DIST / "news" / post["slug"]
        post_dir.mkdir(parents=True, exist_ok=True)
        html = env.get_template("post.html").render(
            **common,
            url=make_url("../../"),
            path=post["url"],
            title=f"{post['title']} — {cfg['site_name']}",
            description=post["excerpt"],
            og_type="article",
            og_image=post["cover"],
            schema=article_schema(cfg, post),
            post=post,
        )
        (post_dir / "index.html").write_text(html, encoding="utf-8")
        pages.append((post["url"], 0.5, "monthly", [(abs_url(post["cover"]), post["title"])]))

    # ---- Copy static assets ----
    shutil.copytree(ASSETS, DIST / "assets")

    # ---- sitemap.xml (with the Google image-sitemap extension) ----
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
             '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    for path, priority, changefreq, images in pages:
        lines.append("  <url>")
        lines.append(f"    <loc>{xml_escape(cfg['site_url'] + path)}</loc>")
        lines.append(f"    <changefreq>{changefreq}</changefreq>")
        lines.append(f"    <priority>{priority}</priority>")
        for img_loc, img_caption in images:
            lines.append("    <image:image>")
            lines.append(f"      <image:loc>{xml_escape(img_loc)}</image:loc>")
            lines.append(f"      <image:caption>{xml_escape(img_caption)}</image:caption>")
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
        title=f"{cfg['site_name']} — {cfg['studio_name']}",
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
