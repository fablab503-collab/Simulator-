"""Works out what kind of file this is and which system should run it.

Looks at the file's contents first (its "magic" bytes), because names can be
wrong, and falls back to the file extension.

Usage: python3 route-file.py <file>...
Prints one JSON object per file, e.g.
  {"file": "app.apk", "kind": "android-app", "system": "android", ...}
On GitHub Actions it also writes one step output per system (android,
windows, mac, linux): the JSON list of files that system should run, or [].
"""
import json
import os
import sys
import zipfile

# Extensions that only mean one thing. (Genesis games also use ".md", like
# Markdown notes, so those are recognized by the "SEGA" stamp inside instead.)
ROMS = {".nes": "nes", ".sfc": "snes", ".smc": "snes", ".gb": "gb", ".gbc": "gb",
        ".gba": "gba", ".gen": "genesis", ".smd": "genesis"}
CODE = {".rs": "rust", ".py": "python", ".java": "java", ".c": "c", ".cpp": "cpp",
        ".js": "javascript", ".go": "go", ".sh": "shell"}
VIDEO = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"}
AUDIO = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}
IMAGE = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
TEXT = {".txt", ".md", ".json", ".csv", ".xml", ".yml", ".yaml", ".toml", ".log"}

# (kind, system, description). "system" is which machine gets the file:
# android, windows, mac, linux (the Linux runner also boots discs in QEMU and
# runs the game emulators).
KINDS = {
    "android-app": ("android", "Android app (APK)"),
    "windows-program": ("windows", "Windows program (EXE)"),
    "windows-installer": ("windows", "Windows installer (MSI)"),
    "mac-disk-image": ("mac", "Mac app in a disk image (DMG)"),
    "mac-installer": ("mac", "Mac installer (PKG)"),
    "mac-app-zip": ("mac", "Mac app in a zip"),
    "disc-image": ("linux", "Bootable disc image (ISO), started in QEMU"),
    "linux-appimage": ("linux", "Linux app (AppImage)"),
    "linux-deb": ("linux", "Linux package for Ubuntu/Debian (DEB)"),
    "linux-rpm": ("linux", "Linux package for Fedora/openSUSE (RPM)"),
    "linux-program": ("linux", "Linux program (ELF)"),
    "game-rom": ("linux", "Game for a retro console"),
    "web-page": ("linux", "Web page (HTML)"),
    "pdf": ("linux", "PDF document"),
    "ebook": ("linux", "E-book (EPUB)"),
    "video": ("linux", "Video"),
    "audio": ("linux", "Audio"),
    "image": ("linux", "Picture"),
    "code": ("linux", "Source code"),
    "text": ("linux", "Text"),
    "zip": ("linux", "Zip archive"),
    "unknown": ("linux", "Unknown file"),
}


def head(path, n=0x9000):
    with open(path, "rb") as f:
        return f.read(n)


def classify(path):
    """Returns (kind, extra) where extra is e.g. the console or language."""
    ext = os.path.splitext(path)[1].lower()
    data = head(path)

    # Contents first.
    if len(data) > 0x8006 and data[0x8001:0x8006] == b"CD001":
        return "disc-image", ""
    if data[:4] == b"\x7fELF":
        if data[8:11] == b"AI\x02":
            return "linux-appimage", ""
        return "linux-program", ""
    if data[:2] == b"MZ":
        return "windows-program", ""
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" and ext == ".msi":
        return "windows-installer", ""
    if data[:8] == b"!<arch>\n" and b"debian-binary" in data[:200]:
        return "linux-deb", ""
    if data[:4] == b"\xed\xab\xee\xdb":
        return "linux-rpm", ""
    if data[:4] == b"xar!":
        return "mac-installer", ""
    if data[:5] == b"%PDF-":
        return "pdf", ""
    if data[:4] == b"NES\x1a":
        return "game-rom", "nes"
    if data[0x100:0x104] == b"SEGA":
        return "game-rom", "genesis"
    if data[0x104:0x108] == b"\xce\xed\x66\x66":  # the Nintendo logo every Game Boy game carries
        return "game-rom", "gb"
    if data[0x04:0x08] == b"\x24\xff\xae\x51":  # the same for Game Boy Advance
        return "game-rom", "gba"
    if data[:2] == b"PK" and zipfile.is_zipfile(path):
        names = zipfile.ZipFile(path).namelist()
        if "AndroidManifest.xml" in names:
            return "android-app", ""
        if "mimetype" in names and zipfile.ZipFile(path).read("mimetype").startswith(b"application/epub"):
            return "ebook", ""
        if any(".app/Contents/" in n for n in names):
            return "mac-app-zip", ""
        return "zip", ""

    # Then the name.
    if ext == ".dmg":
        return "mac-disk-image", ""
    if ext == ".msi":
        return "windows-installer", ""
    if ext in ROMS:
        return "game-rom", ROMS[ext]
    if ext in (".html", ".htm"):
        return "web-page", ""
    if ext in VIDEO:
        return "video", ""
    if ext in AUDIO:
        return "audio", ""
    if ext in IMAGE:
        return "image", ""
    if ext in CODE:
        return "code", CODE[ext]
    if data.lstrip()[:15].lower().startswith((b"<!doctype html", b"<html")):
        return "web-page", ""
    if ext in TEXT:
        return "text", ""
    try:
        data.decode("utf-8")
        return "text", ""
    except UnicodeDecodeError:
        return "unknown", ""


def route(path):
    kind, extra = classify(path)
    system, detail = KINDS[kind]
    if extra:
        detail += " (%s)" % extra
    return {"file": os.path.basename(path), "kind": kind, "system": system,
            "detail": detail, "extra": extra}


def main():
    results = [route(p) for p in sys.argv[1:]]
    for r in results:
        print(json.dumps(r))
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            for system in ("android", "windows", "mac", "linux"):
                mine = [r for r in results if r["system"] == system]
                f.write("%s=%s\n" % (system, json.dumps(mine)))

if __name__ == "__main__":
    main()
