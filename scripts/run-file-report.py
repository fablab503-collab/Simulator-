"""Combines the results of a Gimmich "run this file" job into one report.

Usage: python3 run-file-report.py <results-dir> <out-dir>
<results-dir> holds one folder per system that ran a file (each with
result.png and result.txt). Writes report.md and report.png to <out-dir>.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

src, out = sys.argv[1], sys.argv[2]
os.makedirs(src, exist_ok=True)
os.makedirs(out, exist_ok=True)


def font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/" + name, size)
    except OSError:
        return ImageFont.load_default()


results = []
for folder in sorted(os.listdir(src)):
    path = os.path.join(src, folder)
    if not os.path.isdir(path):
        continue
    note = os.path.join(path, "result.txt")
    lines = open(note).read().splitlines() if os.path.exists(note) else ["(no result: the job failed early)"]
    picture = os.path.join(path, "result.png")
    results.append((folder.removeprefix("result-"), lines, picture if os.path.exists(picture) else None))

with open(os.path.join(out, "report.md"), "w") as f:
    f.write("# Gimmich run report\n\n")
    for name, lines, picture in results:
        failed = any(l.startswith("Result: failed") for l in lines) or lines[0].startswith("(no result")
        f.write("## %s %s\n\n" % ("❌" if failed else "✅", name))
        f.write("\n".join("- " + l for l in lines) + "\n\n")

# One picture: a row per file, with what the system showed and its notes.
TW, TH, PAD = 640, 400, 24
H = 100 + max(1, len(results)) * (TH + PAD)
sheet = Image.new("RGB", (TW * 2 + PAD * 3, H), (243, 246, 249))
d = ImageDraw.Draw(sheet)
d.text((PAD, 30), "Gimmich run · %d file%s" % (len(results), "" if len(results) == 1 else "s"),
       font=font(40, True), fill=(22, 33, 46))
y = 100
for name, lines, picture in results:
    d.rectangle([PAD, y, PAD + TW, y + TH], fill=(226, 232, 239))
    if picture:
        im = Image.open(picture).convert("RGB")
        im.thumbnail((TW, TH))
        sheet.paste(im, (PAD + (TW - im.width) // 2, y + (TH - im.height) // 2))
    x = PAD * 2 + TW
    d.text((x, y), name, font=font(24, True), fill=(22, 33, 46))
    for i, line in enumerate(lines[:12]):
        d.text((x, y + 40 + 28 * i), line[:60], font=font(18), fill=(90, 104, 120))
    y += TH + PAD
sheet.save(os.path.join(out, "report.png"))
print("Report: %d result(s)" % len(results))
