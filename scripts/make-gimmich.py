"""Builds the Gimmich bundle: every system's screenshots in one folder,
one picture showing all of them (each labeled with its exact version), and a
list of every version.

Usage: python3 make-gimmich.py <artifacts-dir> <out-dir>
<artifacts-dir> holds one folder per downloaded GitHub artifact,
for example "linux-ubuntu-screenshots/".
"""
import os
import shutil
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gimmich_labels import GROUPS, is_main_photo, natural, photo_title, read_info  # noqa: E402

src, out = sys.argv[1], sys.argv[2]
os.makedirs(src, exist_ok=True)   # no photos at all still makes an (empty) bundle
os.makedirs(out, exist_ok=True)

tiles = {key: [] for key, _ in GROUPS}
versions = []
for folder in sorted(os.listdir(src), key=natural):
    path = os.path.join(src, folder)
    if not os.path.isdir(path):
        continue
    system = folder.removesuffix("-screenshots")
    group = system.split("-")[0]
    dest = os.path.join(out, group, system)
    os.makedirs(dest, exist_ok=True)
    names = sorted(os.listdir(path))

    # Read this system's version first, so every photo can carry it.
    texts, version, devices = read_info(path, names, group)
    versions += ["- **" + system + "**: " + text for text in texts]

    for name in names:
        if name.endswith(".png") and not is_main_photo(folder, name):
            continue  # skip the in-between photos to keep the download small
        shutil.copy(os.path.join(path, name), dest)
        if is_main_photo(folder, name) and group in tiles:
            title = photo_title(group, system, name[:-4], version, devices)
            tiles[group].append((title, system, os.path.join(dest, name)))

with open(os.path.join(out, "versions.md"), "w") as f:
    f.write("# Gimmich versions\n\n" + "\n".join(versions) + "\n")


def font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/" + name, size)
    except OSError:
        return ImageFont.load_default()


def fit(text, fnt, width):
    """Shortens text with an ellipsis so it fits in width pixels."""
    if fnt.getlength(text) <= width:
        return text
    while text and fnt.getlength(text + "…") > width:
        text = text[:-1]
    return text + "…"


TW, TH, PAD, COLS, LABEL_H = 420, 300, 24, 4, 74
title_font, sub_font = font(22, True), font(16)
total = sum(len(v) for v in tiles.values())
rows = sum((len(v) + COLS - 1) // COLS for v in tiles.values())
groups = sum(1 for v in tiles.values() if v)
W = PAD + COLS * (TW + PAD)
H = 110 + groups * 60 + rows * (TH + LABEL_H + PAD) + 20
sheet = Image.new("RGB", (W, H), (243, 246, 249))
d = ImageDraw.Draw(sheet)
d.text((PAD, 30), "Gimmich · %d screens" % total, font=font(44, True), fill=(22, 33, 46))
y = 110
for key, title in GROUPS:
    items = tiles[key]
    if not items:
        continue
    d.text((PAD, y), "%s (%d)" % (title, len(items)), font=font(30, True), fill=(90, 104, 120))
    y += 50
    for i, (label, system, file) in enumerate(items):
        if i and i % COLS == 0:
            y += TH + LABEL_H + PAD
        x = PAD + (i % COLS) * (TW + PAD)
        im = Image.open(file).convert("RGB")
        im.thumbnail((TW, TH))
        d.rectangle([x, y, x + TW, y + TH], fill=(226, 232, 239))
        sheet.paste(im, (x + (TW - im.width) // 2, y + (TH - im.height) // 2))
        d.text((x, y + TH + 10), fit(label, title_font, TW), font=title_font, fill=(22, 33, 46))
        d.text((x, y + TH + 40), fit(system, sub_font, TW), font=sub_font, fill=(90, 104, 120))
    y += TH + LABEL_H + PAD
sheet.crop((0, 0, W, y)).save(os.path.join(out, "gimmich-all.png"))
print("Gimmich: %d screens, %d version lines" % (total, len(versions)))
