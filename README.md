# Cubic — website

Static marketing site for **Cubic** (Twin Turtle Games). Built as plain HTML/CSS/JS,
generated from templates + Markdown by a small Python build script, and deployed to
GitHub Pages automatically on every push via GitHub Actions.

## ⚠️ Things to fix before launch

1. **`assets/images/logo-color-placeholder.png`** — this is a generated placeholder
   (a duotone recolor of the grayscale logo), standing in for the real full-color Cubic
   logo, which wasn't included in the upload batch. Drop the real file in at
   `assets/images/logo-color-placeholder.png` (or update the `src` in
   `templates/index.html`'s `.hero-logo`) once you have it.
2. **GIFs** (`assets/images/gifs/gameplay-1.gif`, `gameplay-2.gif`) — placeholders.
   Replace with real gameplay capture.
3. **Screenshots** (`assets/images/screenshots/screenshot-1.jpg` … `-6.jpg`) — placeholders
   cropped from your background art. Replace with real screenshots (any filenames matching
   `screenshot-*.jpg` — the carousel, homepage news thumbnails, and press kit all pick them
   up automatically).
4. **Key art** (`assets/images/keyart/keyart-1` … `keyart-7`, each with `.svg`, `-1x.png`,
   `-2x.png`, `.ai.txt`) — placeholders. Replace each file with the real export, **keeping
   the same filenames** so the press kit keeps working.
5. **`content/config.yaml`** — set `site_url` to your real GitHub Pages URL (or custom
   domain), and fill in the real Discord / YouTube / Twitter / Instagram / Steam links.
6. **Newsletter** — `subscribe-form` posts to `newsletter_endpoint` in `config.yaml`. Point
   it at your provider (Buttondown, Mailchimp, ConvertKit, etc.) — right now it just shows a
   local "thanks" message without sending anywhere.

## How the site is put together

```
content/
  config.yaml        ← site name, links, Steam URL, contact email, trailer video id
  posts/*.md          ← one file per blog post (see below)
  legal/terms.md
  legal/privacy.md
templates/             ← Jinja2 HTML templates (navbar/footer live in base.html)
assets/                ← CSS, JS, images/gifs — copied into the site as-is
scripts/build.py       ← generates everything below into dist/
dist/                  ← build output (git-ignored — this is what gets deployed)
```

Running `python3 scripts/build.py` reads `content/`, renders the templates, and writes a
complete static site to `dist/`: the homepage, `/news/` index, one page per blog post,
`/presskit.html`, `/terms.html`, `/privacy.html`, `sitemap.xml`, and `robots.txt`.

### Writing a new blog post

Add a Markdown file to `content/posts/`, named however you like (the date prefix is
optional and stripped from the URL), e.g. `content/posts/2026-07-01-new-devlog.md`:

```md
---
title: "My New Devlog"
date: 2026-07-01
author: "Your Name"
excerpt: "One or two sentences — this is what shows on the news list and homepage."
cover: /assets/images/screenshots/screenshot-2.jpg
---

Write the post body here in **Markdown**. Headings, links, images, lists — all fine.
```

`author` is optional. When set, it shows as a small "Author: [name]" line on that post's
own page only (not on the news list or homepage cards). Leave it out and nothing renders.

Push it to `main`. GitHub Actions rebuilds the whole site — including the new post's own
page at `/news/new-devlog/`, its card on `/news/`, and (if it's one of the 3 newest) its
card on the homepage — and redeploys automatically. You never hand-edit HTML for a post.

### Local preview

```
pip install -r requirements.txt
python3 scripts/build.py
```

That's it — every page in `dist/` uses relative links, so you can just **double-click
`dist/index.html`** and it'll open correctly in your browser with full CSS, no local
server required. (A local server works too, if you prefer: `cd dist && python3 -m
http.server 8000` → `http://localhost:8000`.)

## Deploying (one-time setup)

1. Push this repo to GitHub.
2. In the repo, go to **Settings → Pages** and set **Source** to **GitHub Actions**.
3. Push to `main` (or run the "Build and deploy site" workflow manually). The site will be
   live at `https://<your-username>.github.io/<repo-name>/` (or your custom domain, if you
   configure one under Settings → Pages, in which case also update `site_url` in
   `content/config.yaml` to match).

## Language switcher

The EN/DA toggle in the navbar swaps text client-side via `data-i18n` attributes and the
dictionaries in `assets/js/main.js` (`STRINGS.en` / `STRINGS.da`). It currently covers the
homepage's UI strings; blog posts and the press kit are English-only. If you want fully
translated posts, the simplest approach is a `lang: da` field in post frontmatter and a
second copy of each post — ask if you'd like that wired up.

## SEO

Every page ships a canonical URL, Open Graph + Twitter Card tags, and JSON-LD structured
data (`VideoGame` on the homepage with an embedded trailer `VideoObject`, `NewsArticle` on
each post). `sitemap.xml` includes the Google image-sitemap extension (every screenshot,
GIF, key art piece, and logo, with a caption) and is generated fresh on every build, along
with `robots.txt`.

Config fields that feed directly into SEO output (`content/config.yaml`):
- `trailer_upload_date` — the trailer's real YouTube publish date, used in the `VideoObject`
  structured data. Google uses this, so keep it accurate.
- `default_og_image` — fallback Open Graph/Twitter preview image for pages without a more
  specific one (homepage, press kit, 404).
- `screenshot_captions` — a filename → caption map, used as each screenshot's `alt` text
  (carousel + press kit) and its `<image:caption>` in the sitemap. Any screenshot file not
  listed here just falls back to a generic caption, so it's safe to add new screenshots
  without touching this immediately — but for real SEO value, give each one a real caption.

The homepage's trailer thumbnail (`assets/images/trailer-poster.jpg`) is hosted locally
rather than hotlinked from YouTube's CDN, so it gets indexed as your own image rather than
YouTube's. It's currently a placeholder — swap it for a real frame from the trailer.
