#!/usr/bin/env python3
"""Prepare uploaded photos for the site: the "adjust the pictures" step in CLAUDE.md.

For every image under media/ (profile photo, media/experience/, media/gallery/):
  - fix orientation from the EXIF tag, then drop all metadata (EXIF, GPS, XMP, ICC text)
  - convert to JPG (HEIC/HEIF needs pillow-heif; PNG/WebP transparency goes onto white)
  - resize so the long edge is at most 2000px (gallery), 1600px (experience), 1400px (profile)
  - optionally crop: profile to 4:5, experience photos to 4:3

Cropping needs a judgment about where the subject is, so it is explicit:
    --crop media/my_photo.jpg=0.5,0.35     centre of the crop as fractions of width,height
    --crop media/experience/fleet-robotics.jpg=0.5,0.5
Files with no --crop entry are centre-cropped only with --center-crop; otherwise they
keep their shape (fine for the gallery, which is any shape).

Usage:
    pip install Pillow pillow-heif
    python3 scripts/process_photos.py --dry-run          # list what would change
    python3 scripts/process_photos.py --center-crop      # process everything
    python3 scripts/process_photos.py media/gallery/IMG_2034.HEIC

The original is replaced by <same name>.jpg (the old file is deleted if the name changed).
"""

import argparse
import os
import sys

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Pillow is required: pip install Pillow pillow-heif")

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIF = True
except ImportError:
    HEIF = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".avif", ".tif", ".tiff", ".bmp"}
QUALITY = 85


def kind(rel):
    """profile, experience, gallery, or None for files the site does not use as photos."""
    parts = rel.split("/")
    if parts[0] != "media":
        return None
    if len(parts) == 2 and os.path.splitext(parts[1])[0].lower() == "my_photo":
        return "profile"
    if len(parts) == 3 and parts[1] == "experience":
        return "experience"
    if len(parts) == 3 and parts[1] == "gallery":
        return "gallery"
    return None


LONG_EDGE = {"profile": 1400, "experience": 1600, "gallery": 2000}
ASPECT = {"profile": (4, 5), "experience": (4, 3)}


def crop_to(img, aspect, cx, cy):
    """Largest crop of the given aspect, centred as close to (cx, cy) as the frame allows."""
    w, h = img.size
    aw, ah = aspect
    if w * ah > h * aw:  # too wide
        cw, ch = round(h * aw / ah), h
    else:  # too tall
        cw, ch = w, round(w * ah / aw)
    left = min(max(round(cx * w - cw / 2), 0), w - cw)
    top = min(max(round(cy * h - ch / 2), 0), h - ch)
    return img.crop((left, top, left + cw, top + ch))


def flatten(img):
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        return bg
    return img.convert("RGB")


def process(rel, crops, center_crop, dry_run):
    k = kind(rel)
    src = os.path.join(ROOT, rel)
    ext = os.path.splitext(rel)[1].lower()
    if k is None or ext not in EXTS:
        return
    if ext in (".heic", ".heif") and not HEIF:
        print("skip %s: install pillow-heif to read HEIC" % rel)
        return
    dst_rel = os.path.splitext(rel)[0] + ".jpg"
    with Image.open(src) as im:
        im.load()
        img = ImageOps.exif_transpose(im)
    before = img.size
    if k in ASPECT and (rel in crops or dst_rel in crops or center_crop):
        cx, cy = crops.get(rel) or crops.get(dst_rel) or (0.5, 0.5)
        img = crop_to(img, ASPECT[k], cx, cy)
    limit = LONG_EDGE[k]
    if max(img.size) > limit:
        scale = limit / max(img.size)
        img = img.resize((round(img.size[0] * scale), round(img.size[1] * scale)), Image.LANCZOS)
    img = flatten(img)
    print("%s %s: %dx%d -> %dx%d%s" % ("would write" if dry_run else "wrote", dst_rel, before[0], before[1],
                                         img.size[0], img.size[1], "" if dst_rel == rel else "  (from %s)" % rel))
    if dry_run:
        return
    clean = Image.new("RGB", img.size)  # a fresh image carries no EXIF/GPS/XMP over
    clean.paste(img)
    tmp = os.path.join(ROOT, dst_rel + ".tmp")
    clean.save(tmp, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    os.replace(tmp, os.path.join(ROOT, dst_rel))
    if dst_rel != rel:
        os.remove(src)


def parse_crops(values):
    crops = {}
    for v in values or []:
        path, _, xy = v.partition("=")
        try:
            cx, cy = (float(t) for t in xy.split(","))
        except ValueError:
            sys.exit("bad --crop %r, expected path=x,y with fractions, e.g. media/my_photo.jpg=0.5,0.4" % v)
        crops[os.path.normpath(path).replace(os.sep, "/")] = (min(max(cx, 0.0), 1.0), min(max(cy, 0.0), 1.0))
    return crops


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="files to process (default: everything under media/)")
    ap.add_argument("--crop", action="append", metavar="PATH=X,Y", help="crop centre for one file, as fractions")
    ap.add_argument("--center-crop", action="store_true", help="centre-crop profile/experience photos with no --crop")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    crops = parse_crops(args.crop)

    if args.paths:
        rels = [os.path.relpath(os.path.abspath(p), ROOT).replace(os.sep, "/") for p in args.paths]
    else:
        rels = []
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, "media")):
            dirnames[:] = sorted(dirnames)
            for name in sorted(filenames):
                rels.append(os.path.relpath(os.path.join(dirpath, name), ROOT).replace(os.sep, "/"))
    for rel in rels:
        process(rel, crops, args.center_crop, args.dry_run)


if __name__ == "__main__":
    main()
