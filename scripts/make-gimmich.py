"""Builds the Gimmich bundle: every system's screenshots in one folder,
one picture showing all of them, and a list of every version.

Usage: python3 make-gimmich.py <artifacts-dir> <out-dir>
<artifacts-dir> holds one folder per downloaded GitHub artifact,
for example "linux-ubuntu-screenshots/".
"""
import os
import re
import shutil
import sys

from PIL import Image, ImageDraw, ImageFont

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)

GROUPS = [("apple", "Apple simulators"), ("mac", "Macs"), ("android", "Android"),
          ("windows", "Windows"), ("linux", "Linux")]


def is_main_photo(folder, name):
    # Linux keeps one photo every 30 seconds ("ubuntu-07.png"); only the main one counts.
    return name.endswith(".png") and not re.search(r"-\d\d\.png$", name)


tiles = {key: [] for key, _ in GROUPS}
versions = []
for folder in sorted(os.listdir(src)):
    path = os.path.join(src, folder)
    if not os.path.isdir(path):
        continue
    system = folder.removesuffix("-screenshots")
    group = system.split("-")[0]
    dest = os.path.join(out, group, system)
    os.makedirs(dest, exist_ok=True)
    for name in sorted(os.listdir(path)):
        if name.endswith(".png") and not is_main_photo(folder, name):
            continue  # skip the in-between Linux photos to keep the download small
        shutil.copy(os.path.join(path, name), dest)
        if is_main_photo(folder, name) and group in tiles:
            stem = name[:-4]
            same = stem.startswith(system) or system.endswith(stem)
            tiles[group].append((system if same else system + ": " + stem, os.path.join(dest, name)))
        if name.endswith("version.txt"):
            with open(os.path.join(path, name)) as f:
                text = " · ".join(l.strip() for l in f if l.strip())
            if group == "android":
                text = "Android " + text
            versions.append("- **" + system + "**: " + text)
        if name == "installed-runtimes.txt":
            with open(os.path.join(path, name)) as f:
                text = " · ".join(l.split(" (")[0].strip() for l in f if re.match(r"(iOS|watchOS) ", l))
            versions.append("- **" + system + "**: " + text)

with open(os.path.join(out, "versions.md"), "w") as f:
    f.write("# Gimmich versions\n\n" + "\n".join(versions) + "\n")


def font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/" + name, size)
    except OSError:
        return ImageFont.load_default()


TW, TH, PAD, COLS = 420, 300, 24, 4
total = sum(len(v) for v in tiles.values())
rows = sum((len(v) + COLS - 1) // COLS for v in tiles.values())
groups = sum(1 for v in tiles.values() if v)
W = PAD + COLS * (TW + PAD)
H = 110 + groups * 60 + rows * (TH + 60 + PAD) + 20
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
    for i, (label, file) in enumerate(items):
        if i and i % COLS == 0:
            y += TH + 60 + PAD
        x = PAD + (i % COLS) * (TW + PAD)
        im = Image.open(file).convert("RGB")
        im.thumbnail((TW, TH))
        d.rectangle([x, y, x + TW, y + TH], fill=(226, 232, 239))
        sheet.paste(im, (x + (TW - im.width) // 2, y + (TH - im.height) // 2))
        d.text((x, y + TH + 10), label[:38], font=font(20), fill=(22, 33, 46))
    y += TH + 60 + PAD
sheet.crop((0, 0, W, y)).save(os.path.join(out, "gimmich-all.png"))
print("Gimmich: %d screens, %d version lines" % (total, len(versions)))
