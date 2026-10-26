"""Builds the Gimmich bundle: every system's screenshots in one folder,
one picture showing all of them (each labeled with its exact version), and a
list of every version.

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
          ("windows", "Windows"), ("linux", "Linux"), ("other", "Other free systems"),
          ("games", "Game consoles (free homebrew only)")]

# Download file name -> short version label, for booted systems.
FILE_LABELS = [
    (r"warty-release", lambda m: "Ubuntu 4.10"),
    (r"ubuntu-([\d.]+)-desktop", lambda m: "Ubuntu " + m[1]),
    (r"Fedora-Workstation-Live-(\d+)", lambda m: "Fedora " + m[1]),
    (r"debian-live-([\d.]+)", lambda m: "Debian " + m[1]),
    (r"linuxmint-([\d.]+)", lambda m: "Linux Mint " + m[1]),
    (r"archlinux-([\d.]+)-", lambda m: "Arch Linux " + m[1]),
    (r"archlinux", lambda m: "Arch Linux"),
    (r"Tumbleweed.*Snapshot(\d+)", lambda m: "openSUSE Tumbleweed " + m[1]),
    (r"Tumbleweed", lambda m: "openSUSE Tumbleweed"),
    (r"pop-os_([\d.]+)", lambda m: "Pop!_OS " + m[1]),
    (r"omarchy-(\d+(?:\.\d+)*)", lambda m: "Omarchy " + m[1]),
    (r"ReactOS-([\d.]+)", lambda m: "ReactOS " + m[1]),
    (r"FD(\d)(\d)", lambda m: "FreeDOS %s.%s" % (m[1], m[2])),
    (r"haiku-r(\d)beta(\d)", lambda m: "Haiku R%s/beta%s" % (m[1], m[2])),
    (r"FreeBSD-([\d.]+)-RELEASE", lambda m: "FreeBSD " + m[1]),
    (r"chromeos_([\d.]+)", lambda m: "ChromeOS Flex " + m[1]),
    (r"latest\.bin", lambda m: "ChromeOS Flex"),
]
# Homebrew file names -> the game's real name, where they differ.
GAME_NAMES = {"240pTestSuitePS1-EMU": "240p Test Suite", "cube": "Cube Test",
              "KeepingSNESalive": "Keeping SNES Alive"}
CONSOLES = {"nes": "NES", "snes": "SNES", "gb": "Game Boy", "gba": "Game Boy Advance",
            "genesis": "Sega Genesis", "ps1": "PlayStation", "psp": "PSP",
            "gamecube": "GameCube", "ps2": "PlayStation 2", "ps3": "PlayStation 3",
            "ps4": "PlayStation 4"}


def short_version(system, group, text):
    """Turns a system's version.txt into a short label like 'Fedora 44'."""
    if group in ("linux", "other"):
        for pattern, label in FILE_LABELS:
            m = re.search(pattern, text)
            if m:
                return label(m)
    if group == "mac":
        os_v = re.search(r"macOS [\d.]+", text)
        chip = "Intel" if "Intel" in text else (re.search(r"Apple M\d+", text) or [""])[0]
        return " · ".join(x for x in [os_v[0] if os_v else "", chip] if x)
    if group == "windows":
        name = re.search(r"OsName\s*:\s*Microsoft (.+?)(?: Datacenter| Enterprise)?\s*·", text)
        build = re.search(r"OsBuildNumber\s*:\s*(\d+)", text)
        return " · ".join(x for x in [name[1] if name else "Windows", "build " + build[1] if build else ""] if x)
    if group == "android":
        api = re.search(r"api-(\d+)", system)
        return text + (" (API %s)" % api[1] if api else "")
    if group == "games":
        console = CONSOLES.get(system.split("-", 1)[1], system)
        game = re.search(r'homebrew "([^"]+?)(\.\w+)?"', text)
        app = re.search(r"net\.\w+\.(\w+) ([\w.\-]+)", text)
        if game:
            return "%s · %s" % (console, GAME_NAMES.get(game[1], game[1]))
        if app:
            return "%s · %s %s" % (console, app[1], app[2])
        return console
    return text


def is_main_photo(folder, name):
    # Booted systems keep one photo every 30 seconds ("ubuntu-07.png"); only
    # their main one counts. (Android's "android-api-21.png" is a main photo.)
    if folder.startswith(("linux-", "other-")) and re.search(r"-\d\d\.png$", name):
        return False
    if folder.startswith("games-") and re.search(r"-1\.png$", name):
        return False
    return name.endswith(".png")


def natural(name):
    """Sort key that puts 'ubuntu-4.10' before 'ubuntu-10.04'."""
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", name)]


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
    version, devices = "", {}
    for name in names:
        file = os.path.join(path, name)
        if name.endswith("version.txt"):
            with open(file) as f:
                text = " · ".join(l.strip() for l in f if l.strip())
            if group == "android":
                text = "Android " + text
            versions.append("- **" + system + "**: " + text)
            version = short_version(system, group, text)
        if name == "installed-runtimes.txt":
            with open(file) as f:
                text = " · ".join(l.split(" (")[0].strip() for l in f if re.match(r"(iOS|watchOS) ", l))
            versions.append("- **" + system + "**: " + text)
        if name == "devices.txt":
            # "iPhone - iPhone 17 Pro: iOS 26.5" -> which version each photo shows
            with open(file) as f:
                for line in f:
                    photo, _, v = line.strip().rpartition(": ")
                    devices[photo] = v

    for name in names:
        if name.endswith(".png") and not is_main_photo(folder, name):
            continue  # skip the in-between photos to keep the download small
        shutil.copy(os.path.join(path, name), dest)
        if is_main_photo(folder, name) and group in tiles:
            stem = name[:-4]
            if group == "apple":
                # "iPhone - iPhone Duo (screen 3)" -> "iPhone Duo (screen 3) · iOS 27.1"
                device = stem.split(" - ", 1)[-1]
                v = next((v for p, v in devices.items() if stem.startswith(p)), "")
                if not v and system.split("-")[-1].isdigit():
                    # Older runs have no devices.txt: use the group's major version.
                    major = int(system.split("-")[-1])
                    if stem.startswith("Apple Watch"):
                        v = "watchOS %d" % (major if major >= 26 else major - 7)
                    else:
                        v = ("iPadOS %d" if stem.startswith("iPad") else "iOS %d") % major
                title = " · ".join(x for x in [device, v] if x)
            else:
                title = version or system
                if not (stem.startswith(system) or system.endswith(stem)) and group != "games":
                    title += " (" + stem + ")"
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
