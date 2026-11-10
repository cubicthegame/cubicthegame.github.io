"""Build display images separately from the original downloadable assets."""
import hashlib
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
import xml.etree.ElementTree as ET

from PIL import Image, ImageOps


class Media:
    def __init__(self, assets, output):
        self.assets = Path(assets).resolve()
        self.output = Path(output)
        self.cache = {}

    def image(self, path, widths=(480, 800, 1280), social=False):
        key = (path, tuple(widths), social)
        if key in self.cache:
            return self.cache[key]
        if urlsplit(path).scheme or path.startswith("//"):
            return {"src": path, "candidates": []}
        source = (self.assets.parent / unquote(path.lstrip("/"))).resolve()
        if not source.is_relative_to(self.assets):
            raise ValueError(f"Image must be inside assets: {path}")
        if source.suffix.lower() == ".svg":
            # SVG is already scalable. Keep it intact, including SVG-only items.
            svg = ET.parse(source).getroot()
            box = svg.get("viewBox", "").replace(",", " ").split()
            result = {"src": path, "candidates": []}
            if len(box) == 4:
                result.update(width=round(float(box[2])), height=round(float(box[3])))
        else:
            with Image.open(source) as original:
                if getattr(original, "is_animated", False):
                    return {"src": path, "candidates": [], "width": original.width, "height": original.height}
                image = ImageOps.exif_transpose(original)
                image = image.convert("RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB")
                profile = original.info.get("icc_profile")
                digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
                relative = source.relative_to(self.assets).with_suffix("")
                candidates = []
                sizes = sorted({min(int(width), image.width) for width in widths})
                if not sizes or sizes[0] <= 0:
                    raise ValueError("Image widths must be positive")
                for width in sizes:
                    height = max(1, round(image.height * width / image.width))
                    resized = image.resize((width, height), Image.Resampling.LANCZOS)
                    transparent = resized.mode == "RGBA" and resized.getextrema()[3][0] < 255
                    extension = ("png" if transparent else "jpg") if social else "webp"
                    destination = self.output / "generated" / relative.parent / f"{relative.name}-{digest}-{width}.{extension}"
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    options = {"icc_profile": profile} if profile else {}
                    if extension == "webp":
                        options.update(lossless=True, method=6)
                    elif extension == "jpg":
                        resized = resized.convert("RGB")
                        options.update(quality=90, optimize=True, progressive=True)
                    else:
                        options.update(optimize=True)
                    resized.save(destination, **options)
                    candidates.append({
                        "path": "/assets/" + quote(destination.relative_to(self.output).as_posix()),
                        "width": width,
                        "height": height,
                    })
                # A small fallback is sufficient; srcset supplies larger displays.
                result = {"src": candidates[0]["path"], "width": candidates[0]["width"],
                          "height": candidates[0]["height"], "candidates": candidates}
        self.cache[key] = result
        return result
