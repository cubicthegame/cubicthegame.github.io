# Updating the press kit

Press kit downloads live in `assets/presskit/<category>/<item>/`.
The build discovers categories, items, previews, and downloads automatically.
Folder names become headings, so use readable names separated by hyphens.

For example:

```text
assets/presskit/key-art/new-art/
  new-art-1x.png
  new-art-2x.png
  new-art.svg
  new-art.ai
```

Each item needs at least one PNG, JPG, JPEG, WebP, or SVG for its preview.
The smallest raster image is used for the preview, falling back to SVG.
Only files that exist get download buttons. PDF, EPS, PSD, and ZIP downloads
are also supported. Name scaled exports with `-1x`, `-2x`, etc. (or `@1x`,
`@2x`) immediately before the extension to show the scale on the button.
The imported PNGs were renamed from the original 2x/4x to the correct 1x/2x;
their image data and dimensions are unchanged.

All discovered images are included in the press kit's image sitemap entry.
Illustrator and other source files are linked as downloads, not image entries.
The press kit has no separate Screenshots section. Files in
`assets/images/screenshots/` remain available to other pages.

Run `python scripts/build.py` to preview changes in `dist/presskit.html`.
Push changes to `main` for the existing GitHub Pages workflow to rebuild and
deploy the page, assets, sitemap.xml, and robots.txt. GitHub Pages cannot scan
folders at runtime; discovery happens on every build.
