"""How Gimmich names things: the groups, and the short version label under
each photo (like "Fedora 44" or "iPhone 17 Pro · iOS 26.5").

Shared by make-gimmich.py (the bundle and its big picture) and
gimmich-viewer.py (the viewer app), so both always say the same thing.
Needs only Python 3.9+.
"""
import os
import re

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


def read_info(path, names, group):
    """Reads one system's notes. Returns (texts, version, devices):
    texts    each full version line, for versions.md
    version  the short label (see short_version)
    devices  Apple only: which version each photo shows, e.g.
             {"iPhone - iPhone 17 Pro": "iOS 26.5"}
    """
    system = os.path.basename(path).removesuffix("-screenshots")
    texts, version, devices = [], "", {}
    for name in names:
        file = os.path.join(path, name)
        if name.endswith("version.txt"):
            with open(file) as f:
                text = " · ".join(l.strip() for l in f if l.strip())
            if group == "android":
                text = "Android " + text
            texts.append(text)
            version = short_version(system, group, text)
        if name == "installed-runtimes.txt":
            with open(file) as f:
                texts.append(" · ".join(l.split(" (")[0].strip() for l in f if re.match(r"(iOS|watchOS) ", l)))
        if name == "devices.txt":
            # "iPhone - iPhone 17 Pro: iOS 26.5" -> which version each photo shows
            with open(file) as f:
                for line in f:
                    photo, _, v = line.strip().rpartition(": ")
                    devices[photo] = v
    return texts, version, devices


def photo_title(group, system, stem, version, devices):
    """The label under one photo; stem is its file name without ".png"."""
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
        return " · ".join(x for x in [device, v] if x)
    title = version or system
    if not (stem.startswith(system) or system.endswith(stem)) and group != "games":
        title += " (" + stem + ")"
    return title
