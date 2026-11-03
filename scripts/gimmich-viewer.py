#!/usr/bin/env python3
"""Gimmich Viewer: see every system Gimmich photographed, on your own computer.

Opens a page in your browser with every system's picture, grouped like the
bundle (Apple, Macs, Android, Windows, Linux, other systems, game consoles)
and labeled with its exact version. Click a picture to see it big.

  python3 scripts/gimmich-viewer.py                  start it
  python3 scripts/gimmich-viewer.py ~/Downloads/gimmich   also show this folder
  On a Mac you can also double-click "Gimmich Viewer.command".

Buttons on the page:
  Get the newest from GitHub   downloads the weekly bundle (about 55 MB)
  Take pictures on this Mac    Macs only: photographs this Mac's newest
                               iPhone, iPad and Apple Watch simulators, and
                               its screen (your wallpaper and windows are
                               left alone)

Everything is kept in ~/Gimmich (choose another folder with --data). Only this
computer can open the page. Needs only Python 3.9 or newer (a Mac has it once
Xcode or its command line tools are installed).
"""
import argparse
import datetime
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gimmich_labels as gl  # noqa: E402

REPO = "fablab503-collab/Simulator-"
RELEASE_API = "https://api.github.com/repos/%s/releases/tags/gimmich-latest" % REPO
BUNDLE_URL = "https://github.com/%s/releases/download/gimmich-latest/gimmich.zip" % REPO
IS_MAC = sys.platform == "darwin"
GROUP_KEYS = [key for key, _ in gl.GROUPS]
PHOTO_TYPES = {".png": "image/png"}


# --- What the viewer is busy with ----------------------------------------

class Job:
    """One thing at a time: a download, or taking pictures. The page asks
    for its state every second while it runs."""

    def __init__(self):
        self.lock = threading.Lock()
        self.state = {"kind": None, "running": False, "message": "", "progress": None, "error": "", "log": []}

    def start(self, kind, work, *args):
        with self.lock:
            if self.state["running"]:
                return False
            self.state = {"kind": kind, "running": True, "message": "Starting…", "progress": None,
                          "error": "", "log": []}
        threading.Thread(target=self._run, args=(work, args), daemon=True).start()
        return True

    def _run(self, work, args):
        try:
            work(self, *args)
        except Exception as e:  # shown on the page instead of lost in the terminal
            self.update(error=str(e) or e.__class__.__name__, message="Stopped.")
        finally:
            self.update(running=False)

    def update(self, **changes):
        with self.lock:
            self.state.update(changes)

    def log(self, line):
        with self.lock:
            self.state["log"] = (self.state["log"] + [line])[-300:]

    def snapshot(self):
        with self.lock:
            return dict(self.state, log=list(self.state["log"]))


# --- Getting the newest bundle from GitHub -------------------------------

def fetch(url, accept=None):
    """Small downloads (the release details). curl first: a Mac's own Python
    can lack the certificates that HTTPS needs, curl never does."""
    if shutil.which("curl"):
        cmd = ["curl", "-fsSL", "--retry", "2"] + (["-H", "Accept: " + accept] if accept else []) + [url]
        return subprocess.run(cmd, check=True, capture_output=True, timeout=60).stdout
    request = urllib.request.Request(url, headers={"Accept": accept} if accept else {})
    with urllib.request.urlopen(request, timeout=60) as r:
        return r.read()


def download(job, url, dest, size):
    if shutil.which("curl"):
        p = subprocess.Popen(["curl", "-fsSL", "--retry", "3", "-o", dest, url], stderr=subprocess.PIPE)
        while p.poll() is None:
            if size and os.path.exists(dest):
                job.update(progress=min(os.path.getsize(dest) / size, 1.0))
            time.sleep(0.3)
        if p.returncode:
            raise RuntimeError("The download failed: " + p.stderr.read().decode(errors="replace").strip())
        return
    with urllib.request.urlopen(url, timeout=60) as r, open(dest, "wb") as f:
        got = 0
        for chunk in iter(lambda: r.read(1 << 20), b""):
            f.write(chunk)
            got += len(chunk)
            if size:
                job.update(progress=min(got / size, 1.0))


def unzip(zip_path, dest):
    """Unpacks, refusing any file that would land outside dest."""
    root = os.path.realpath(dest)
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            target = os.path.realpath(os.path.join(root, info.filename))
            if target != root and not target.startswith(root + os.sep):
                raise RuntimeError("The bundle has an unsafe file name: " + info.filename)
        z.extractall(root)


def get_latest(job, data):
    job.update(message="Asking GitHub for the newest bundle…")
    about, size = {"title": "From GitHub"}, 0
    try:
        release = json.loads(fetch(RELEASE_API, "application/vnd.github+json"))
        about = {"title": release.get("name") or "From GitHub", "published": release.get("published_at", "")}
        size = next((a.get("size", 0) for a in release.get("assets", []) if a.get("name") == "gimmich.zip"), 0)
    except Exception as e:
        job.log("Could not read the release details (%s); downloading anyway." % e)

    part = os.path.join(data, ".gimmich.zip.part")
    job.update(message="Downloading the newest bundle%s…" % (" (%d MB)" % round(size / 1e6) if size else ""),
               progress=0.0 if size else None)
    download(job, BUNDLE_URL, part, size)

    job.update(message="Unpacking…", progress=None)
    new, old, latest = (os.path.join(data, n) for n in (".latest.new", ".latest.old", "latest"))
    for leftover in (new, old):
        shutil.rmtree(leftover, ignore_errors=True)
    unzip(part, new)
    write_about(new, about)
    if os.path.isdir(latest):
        os.rename(latest, old)
    os.rename(new, latest)
    shutil.rmtree(old, ignore_errors=True)
    os.remove(part)
    job.update(message="Done: the newest pictures from GitHub are here.")


# --- Taking pictures on this Mac ------------------------------------------

def run_logged(job, cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in p.stdout:
        job.log(line.rstrip())
    return p.wait()


def output(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def mac_version_text():
    """The same notes screenshot-mac.sh writes, so the label reads the same."""
    arch, brand = platform.machine(), output(["sysctl", "-n", "machdep.cpu.brand_string"])
    if arch == "arm64":
        chip = "Apple " + re.sub(r"^Apple ", "", brand)
    elif arch == "x86_64":
        chip = "Intel (%s)" % brand
    else:
        chip = arch
    xcode = (output(["xcodebuild", "-version"]).splitlines() or [""])[0]
    return "macOS %s (build %s)\nChip: %s\nXcode: %s\n" % (
        output(["sw_vers", "-productVersion"]), output(["sw_vers", "-buildVersion"]), chip, xcode)


def capture(job, data, simulators, screen):
    now = datetime.datetime.now()
    folder = os.path.join(data, "this-mac-" + now.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(folder)
    write_about(folder, {"title": "This Mac · " + now.strftime("%d %b %Y, %H:%M")})
    problems = []

    if simulators:
        if not shutil.which("jq"):
            problems.append("The simulator pictures need jq: it comes with macOS 15 and newer, or install "
                            "it with “brew install jq”.")
        elif subprocess.run(["xcrun", "--find", "simctl"], capture_output=True).returncode:
            problems.append("The simulator pictures need Xcode (free in the App Store), opened once.")
        else:
            job.update(message="Starting the newest iPhone, iPad and Apple Watch simulators, one at a time. "
                               "This takes a few minutes…")
            code = run_logged(job, ["bash", os.path.join(HERE, "screenshot-simulators.sh"),
                                    os.path.join(folder, "apple", "apple-this-mac")])
            if code:
                problems.append("The simulator pictures stopped early (see “What happened”).")

    if screen:
        out = os.path.join(folder, "mac", "mac-this-mac")
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "mac-this-mac-version.txt"), "w") as f:
            f.write(mac_version_text())
        for n in range(5, 0, -1):
            job.update(message="Taking a picture of your screen in %d…" % n)
            time.sleep(1)
        png = os.path.join(out, "mac-this-mac.png")
        result = subprocess.run(["screencapture", "-x", png], capture_output=True, text=True)
        if result.returncode or not os.path.exists(png):
            job.log(result.stderr.strip())
            problems.append("macOS didn't allow the screen picture. Allow Terminal in System Settings → "
                            "Privacy & Security → Screen Recording, then try again.")

    job.update(message="Done: your Mac's pictures are in “This Mac”." if not problems else "Finished, with problems.",
               error=" ".join(problems))


# --- Reading what's on disk ------------------------------------------------

def write_about(folder, about):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, ".about.json"), "w") as f:
        json.dump(about, f)


def read_about(folder):
    try:
        with open(os.path.join(folder, ".about.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def systems_in(root):
    """Every system folder under root: the bundle's <group>/<system>/, or a
    folder of run downloads named <system>-screenshots/. Looks one folder
    deeper if root itself has neither (e.g. the folder a zip was unpacked in)."""
    def scan(folder):
        found = []
        try:
            entries = sorted(os.listdir(folder), key=gl.natural)
        except OSError:
            return found
        for entry in entries:
            path = os.path.join(folder, entry)
            if entry.startswith(".") or not os.path.isdir(path):
                continue
            if entry in GROUP_KEYS:
                for system in sorted(os.listdir(path), key=gl.natural):
                    if os.path.isdir(os.path.join(path, system)):
                        found.append((entry, system, os.path.join(path, system)))
            elif entry.endswith("-screenshots"):
                system = entry[:-len("-screenshots")]
                found.append((system.split("-")[0], system, path))
        return found

    found = scan(root)
    if not found:
        for entry in sorted(os.listdir(root)) if os.path.isdir(root) else []:
            if not entry.startswith("."):
                found += scan(os.path.join(root, entry))
    return found


def sources(server):
    """Everything the viewer can show: (id, title, kind, folder, note)."""
    found, data = [], server.data
    latest = os.path.join(data, "latest")
    if os.path.isdir(latest):
        about = read_about(latest)
        found.append(("github", about.get("title", "From GitHub"), "github", latest, about.get("published", "")))
    for name in sorted(os.listdir(data), reverse=True):  # newest first
        path = os.path.join(data, name)
        if name.startswith("this-mac-") and os.path.isdir(path):
            found.append(("mac-" + name[len("this-mac-"):], read_about(path).get("title", name), "this-mac", path, ""))
    for i, folder in enumerate(server.extra):
        found.append(("folder-%d" % i, "Folder · " + os.path.basename(os.path.normpath(folder)), "folder", folder, folder))
    return found


def library(server):
    shown = []
    for source_id, title, kind, root, note in sources(server):
        groups = {key: [] for key in GROUP_KEYS}
        for group, system, path in systems_in(root):
            if group not in groups:
                continue
            names = sorted(os.listdir(path))
            texts, version, devices = gl.read_info(path, names, group)
            photos = [name for name in names if gl.is_main_photo(system, name)]
            titles = [gl.photo_title(group, system, name[:-4], version, devices) for name in photos]
            for name, label in zip(photos, titles):
                file = os.path.join(path, name)
                rel = os.path.relpath(file, root).replace(os.sep, "/")
                groups[group].append({
                    "title": label,
                    "system": system,
                    # Two photos with the same label (like PS3's): also say which file it is.
                    "sub": system if titles.count(label) == 1 else "%s · %s" % (system, name[:-4]),
                    "details": texts,
                    "photo": "/photo/%s/%s?v=%d" % (source_id, quote(rel), os.path.getmtime(file)),
                })
        shown.append({"id": source_id, "title": title, "kind": kind, "note": note,
                      "groups": [{"key": k, "title": t, "tiles": groups[k]} for k, t in gl.GROUPS if groups[k]]})
    return {"sources": shown, "isMac": IS_MAC}


# --- The web server (only this computer can reach it) ---------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "GimmichViewer"

    def log_message(self, *args):
        pass

    def host_ok(self):
        # Pages from other sites can't read this one: a request must be
        # addressed to this computer's own name, not a borrowed one.
        port = self.server.server_address[1]
        return self.headers.get("Host", "") in ("127.0.0.1:%d" % port, "localhost:%d" % port)

    def send(self, code, body, kind="application/json; charset=utf-8", headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.host_ok():
            return self.send(403, {"error": "Open the viewer at 127.0.0.1."})
        path = urlparse(self.path).path
        if path == "/":
            page = PAGE.replace("__TOKEN__", self.server.token)
            return self.send(200, page, "text/html; charset=utf-8", {
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'none'; img-src 'self'; connect-src 'self'; "
                                           "style-src 'unsafe-inline'; script-src 'unsafe-inline'"})
        if path == "/api/library":
            return self.send(200, library(self.server))
        if path == "/api/status":
            return self.send(200, self.server.job.snapshot())
        if path.startswith("/photo/"):
            return self.photo(path)
        self.send(404, {"error": "Not found."})

    def do_POST(self):
        token = self.headers.get("X-Gimmich-Token", "")
        if not self.host_ok() or not secrets.compare_digest(token, self.server.token):
            return self.send(403, {"error": "Not allowed."})
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}") if length else {}
        except ValueError:
            return self.send(400, {"error": "Bad request."})
        path, job = urlparse(self.path).path, self.server.job
        if path == "/api/get-latest":
            started = job.start("download", get_latest, self.server.data)
        elif path == "/api/capture":
            if not IS_MAC:
                return self.send(400, {"error": "Taking pictures only works on a Mac."})
            started = job.start("capture", capture, self.server.data,
                                bool(body.get("simulators", True)), bool(body.get("screen", True)))
        else:
            return self.send(404, {"error": "Not found."})
        if not started:
            return self.send(409, {"error": "Busy with something else: wait for it to finish."})
        self.send(202, {"started": True})

    def photo(self, path):
        source_id, _, rel = path[len("/photo/"):].partition("/")
        root = next((s[3] for s in sources(self.server) if s[0] == source_id), None)
        if root is None:
            return self.send(404, {"error": "Not found."})
        root = os.path.realpath(root)
        file = os.path.realpath(os.path.join(root, unquote(rel)))
        kind = PHOTO_TYPES.get(os.path.splitext(file)[1].lower())
        if not file.startswith(root + os.sep) or not kind or not os.path.isfile(file):
            return self.send(404, {"error": "Not found."})
        with open(file, "rb") as f:
            self.send(200, f.read(), kind, {"Cache-Control": "private, max-age=86400"})


def main():
    p = argparse.ArgumentParser(description="Gimmich Viewer: see every system's pictures on this computer.")
    p.add_argument("folders", nargs="*", help="more Gimmich folders to show (an unpacked bundle or run download)")
    p.add_argument("--data", default=os.path.join(os.path.expanduser("~"), "Gimmich"),
                   help="where downloads and this Mac's pictures are kept (default ~/Gimmich)")
    p.add_argument("--port", type=int, default=8642, help="default 8642; any free one if that's taken")
    p.add_argument("--no-browser", action="store_true", help="don't open the browser")
    a = p.parse_args()

    os.makedirs(a.data, exist_ok=True)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    except OSError:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    server.token = secrets.token_urlsafe(24)
    server.job = Job()
    server.data = a.data
    server.extra = [os.path.abspath(os.path.expanduser(f)) for f in a.folders]

    url = "http://127.0.0.1:%d/" % server.server_address[1]
    print("Gimmich Viewer is open at %s" % url)
    print("Pictures are kept in %s. Keep this window open; press Ctrl+C to stop." % a.data)
    if not a.no_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="gimmich-token" content="__TOKEN__">
<title>Gimmich Viewer</title>
<style>
:root {
  --bg: #f3f5f8; --panel: #ffffff; --ink: #15202c; --muted: #5b6979; --line: #dde3ea;
  --chip: #e9eef4; --chip-on: #15202c; --chip-on-ink: #ffffff; --accent: #1f6feb; --accent-ink: #ffffff;
  --shot: #e4e9ef; --bad: #b42318; --bad-bg: #fef3f2; --good: #067647;
  --shadow: 0 1px 2px rgba(16, 24, 40, .05), 0 6px 16px rgba(16, 24, 40, .06);
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0e131a; --panel: #161d26; --ink: #e6ecf3; --muted: #93a1b1; --line: #253040;
    --chip: #1f2833; --chip-on: #e6ecf3; --chip-on-ink: #0e131a; --accent: #4c8dff; --accent-ink: #ffffff;
    --shot: #0b1016; --bad: #fda29b; --bad-bg: #2a1614; --good: #75e0a7;
    --shadow: 0 1px 2px rgba(0, 0, 0, .3), 0 6px 16px rgba(0, 0, 0, .25);
    color-scheme: dark;
  }
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
body { margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
button, select, input { font: inherit; color: inherit; }
.wrap { max-width: 1480px; margin: 0 auto; padding: 0 24px; }
header.top { display: flex; gap: 16px; align-items: center; justify-content: space-between; flex-wrap: wrap;
  padding: 22px 0 14px; }
.brand { display: flex; gap: 14px; align-items: center; min-width: 0; }
.logo { width: 44px; height: 44px; border-radius: 12px; flex: none; display: grid; place-items: center;
  background: linear-gradient(135deg, #1f6feb, #8b5cf6); color: #fff; font-weight: 800; font-size: 22px; }
h1 { margin: 0; font-size: 22px; letter-spacing: -.01em; }
.sub { margin: 2px 0 0; color: var(--muted); font-size: 14px; }
.actions { display: flex; gap: 10px; flex-wrap: wrap; }
.btn { border: 1px solid var(--line); background: var(--panel); border-radius: 10px; padding: 9px 14px;
  cursor: pointer; box-shadow: var(--shadow); font-weight: 600; }
.btn:hover { border-color: var(--muted); }
.btn.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }
.btn:disabled { opacity: .5; cursor: default; }
.job { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 12px 16px;
  margin-bottom: 14px; box-shadow: var(--shadow); }
.job .msg { font-weight: 600; }
.job .err { color: var(--bad); background: var(--bad-bg); border-radius: 8px; padding: 8px 10px; margin-top: 8px; }
.bar-track { height: 6px; background: var(--chip); border-radius: 99px; overflow: hidden; margin-top: 10px; }
.bar-fill { height: 100%; width: 0; background: var(--accent); border-radius: 99px; transition: width .3s; }
.bar-track.busy .bar-fill { width: 30%; animation: slide 1.2s ease-in-out infinite; }
@keyframes slide { 0% { margin-left: -30%; } 100% { margin-left: 100%; } }
details.log { margin-top: 8px; color: var(--muted); }
details.log pre { max-height: 220px; overflow: auto; background: var(--bg); padding: 10px; border-radius: 8px;
  font-size: 12px; white-space: pre-wrap; word-break: break-word; }
nav.tools { position: sticky; top: 0; z-index: 5; background: var(--bg); background: color-mix(in srgb, var(--bg) 92%, transparent);
  backdrop-filter: blur(8px); padding: 10px 0; display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
  border-bottom: 1px solid var(--line); }
select, input[type=search] { background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
  padding: 8px 12px; min-width: 0; }
select { max-width: 100%; }
input[type=search] { flex: 1 1 220px; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip { border: 0; background: var(--chip); border-radius: 99px; padding: 6px 12px; cursor: pointer;
  font-size: 13px; font-weight: 600; white-space: nowrap; }
.chip[aria-pressed=true] { background: var(--chip-on); color: var(--chip-on-ink); }
.chip span { opacity: .65; margin-left: 4px; font-weight: 500; }
main { padding: 6px 0 60px; }
section h2 { font-size: 17px; margin: 24px 0 12px; display: flex; align-items: baseline; gap: 8px; }
section h2 small { color: var(--muted); font-weight: 500; font-size: 14px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 14px; }
.tile { display: block; width: 100%; text-align: left; padding: 0; border: 1px solid var(--line);
  background: var(--panel); border-radius: 14px; overflow: hidden; cursor: zoom-in; box-shadow: var(--shadow);
  transition: transform .12s, border-color .12s; }
.tile:hover, .tile:focus-visible { transform: translateY(-2px); border-color: var(--accent); outline: none; }
.shot { height: 170px; background: var(--shot); display: grid; place-items: center; overflow: hidden; }
.shot img { max-width: 100%; max-height: 100%; object-fit: contain; display: block; }
.cap { padding: 10px 12px 12px; }
.cap b { display: block; font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cap span { display: block; color: var(--muted); font-size: 12.5px; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; }
.empty { text-align: center; padding: 70px 20px; color: var(--muted); }
.empty h2 { color: var(--ink); justify-content: center; }
.empty .btn { margin-top: 12px; }
.lightbox { position: fixed; inset: 0; z-index: 20; background: rgba(5, 8, 12, .97); display: none;
  grid-template-rows: minmax(0, 1fr) auto; color: #e6ecf3; }
.lightbox.open { display: grid; }
.lb-stage { position: relative; display: grid; place-items: center; padding: 20px 64px; min-height: 0;
  overflow: hidden; }
.lb-stage img { max-width: 100%; max-height: 100%; min-height: 0; object-fit: contain; border-radius: 6px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, .5); }
.lb-nav { position: absolute; top: 50%; transform: translateY(-50%); width: 44px; height: 44px;
  border-radius: 99px; border: 0; background: rgba(255, 255, 255, .12); color: #fff; font-size: 22px; cursor: pointer; }
.lb-nav:hover { background: rgba(255, 255, 255, .24); }
.lb-prev { left: 12px; } .lb-next { right: 12px; }
.lb-close { position: absolute; top: 12px; right: 12px; transform: none; }
.lb-info { padding: 14px 24px 18px; background: #05080c; display: flex; gap: 16px;
  justify-content: space-between; align-items: flex-start; flex-wrap: wrap; }
.lb-info h3 { margin: 0; font-size: 17px; }
.lb-info p { margin: 3px 0 0; color: #a9b6c5; font-size: 13px; }
.lb-info a { color: #9ec2ff; font-size: 13px; white-space: nowrap; }
dialog { border: 1px solid var(--line); border-radius: 16px; background: var(--panel); color: var(--ink);
  padding: 22px; max-width: 460px; width: calc(100% - 32px); box-shadow: var(--shadow); }
dialog::backdrop { background: rgba(5, 8, 12, .5); }
dialog h2 { margin: 0 0 6px; font-size: 18px; }
dialog p { margin: 0 0 14px; color: var(--muted); }
dialog label { display: flex; gap: 10px; align-items: flex-start; margin: 10px 0; }
dialog label small { display: block; color: var(--muted); }
dialog input[type=checkbox] { width: 18px; height: 18px; margin-top: 2px; }
.row { display: flex; gap: 10px; justify-content: flex-end; margin-top: 18px; }
@media (max-width: 640px) {
  .wrap { padding: 0 16px; }
  .grid { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
  .shot { height: 120px; }
  .lb-stage { padding: 12px 8px 60px; }
  .lb-prev, .lb-next { top: auto; bottom: 8px; transform: none; }
}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <div class="brand">
      <div class="logo" aria-hidden="true">G</div>
      <div><h1>Gimmich Viewer</h1><p class="sub" id="sub">Every system Gimmich photographed, on your computer.</p></div>
    </div>
    <div class="actions">
      <button class="btn" id="get">Get the newest from GitHub</button>
      <button class="btn primary" id="shoot" hidden>Take pictures on this Mac</button>
    </div>
  </header>
  <div class="job" id="job" hidden>
    <div class="msg" id="job-msg"></div>
    <div class="bar-track" id="job-bar"><div class="bar-fill" id="job-fill"></div></div>
    <div class="err" id="job-err" hidden></div>
    <details class="log" id="job-log-box" hidden><summary>What happened</summary><pre id="job-log"></pre></details>
  </div>
  <nav class="tools" id="tools" hidden>
    <select id="source" aria-label="Which pictures"></select>
    <div class="chips" id="chips" role="group" aria-label="Group"></div>
    <input type="search" id="q" placeholder="Find a system: Ubuntu 8.04, PS3, iPad…" aria-label="Find a system">
  </nav>
  <main id="main"></main>
</div>

<div class="lightbox" id="lb" role="dialog" aria-modal="true" aria-label="Picture">
  <div class="lb-stage" id="lb-stage">
    <img id="lb-img" alt="">
    <button class="lb-nav lb-prev" id="lb-prev" aria-label="Previous">‹</button>
    <button class="lb-nav lb-next" id="lb-next" aria-label="Next">›</button>
    <button class="lb-nav lb-close" id="lb-close" aria-label="Close">×</button>
  </div>
  <div class="lb-info">
    <div><h3 id="lb-title"></h3><p id="lb-sys"></p><p id="lb-details"></p></div>
    <div><p id="lb-count"></p><a id="lb-open" target="_blank" rel="noopener">Open full size</a></div>
  </div>
</div>

<dialog id="shoot-dialog">
  <h2>Take pictures on this Mac</h2>
  <p>Real pictures from your own Mac, shown under “This Mac”.</p>
  <label><input type="checkbox" id="opt-sim" checked>
    <span>iPhone, iPad and Apple Watch simulators
      <small>Starts the newest of each, one at a time, then closes them (a few minutes). Needs Xcode.</small></span></label>
  <label><input type="checkbox" id="opt-screen" checked>
    <span>This Mac's screen
      <small>A picture of your screen 5 seconds after you start, as it is: your wallpaper and windows are left alone.</small></span></label>
  <div class="row">
    <button class="btn" id="shoot-cancel">Cancel</button>
    <button class="btn primary" id="shoot-go">Start</button>
  </div>
</dialog>

<script>
"use strict";
const TOKEN = document.querySelector('meta[name="gimmich-token"]').content;
const $ = (id) => document.getElementById(id);
const store = {
  get(k) { try { return localStorage.getItem("gimmich." + k); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem("gimmich." + k, v); } catch (e) {} },
};
let lib = { sources: [], isMac: false };
let state = { source: store.get("source"), group: "all", q: "" };
let shown = [];      // the tiles on screen, in order (for the big view's arrows)
let current = -1;
let wasRunning = false;

function el(tag, attrs, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") n.className = v; else if (k === "text") n.textContent = v; else n.setAttribute(k, v);
  }
  for (const kid of kids) if (kid != null) n.append(kid);
  return n;
}

async function post(path, body) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json", "X-Gimmich-Token": TOKEN },
                                body: JSON.stringify(body || {}) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || "Something went wrong.");
  return data;
}

async function loadLibrary(pick) {
  lib = await (await fetch("/api/library")).json();
  $("shoot").hidden = !lib.isMac;
  if (pick) state.source = pick;
  if (!lib.sources.some((s) => s.id === state.source)) state.source = lib.sources.length ? lib.sources[0].id : null;
  render();
}

function currentSource() { return lib.sources.find((s) => s.id === state.source); }

function matches(tile) {
  const words = state.q.toLowerCase().split(/\s+/).filter(Boolean);
  const hay = (tile.title + " " + tile.sub + " " + tile.details.join(" ")).toLowerCase();
  return words.every((w) => hay.includes(w));
}

function render() {
  const main = $("main");
  main.replaceChildren();
  const src = currentSource();
  $("tools").hidden = !src;
  if (!src) {
    main.append(el("div", { class: "empty" },
      el("h2", { text: "No pictures yet" }),
      el("p", { text: lib.isMac
        ? "Get the newest pictures of every system from GitHub, or take real ones on this Mac."
        : "Get the newest pictures of every system from GitHub." }),
      (() => { const b = el("button", { class: "btn primary", text: "Get the newest from GitHub (about 55 MB)" });
               b.onclick = getLatest; return b; })()));
    $("sub").textContent = "Every system Gimmich photographed, on your computer.";
    return;
  }

  const select = $("source");
  select.replaceChildren(...lib.sources.map((s) => {
    const o = el("option", { value: s.id, text: s.title }); if (s.id === src.id) o.selected = true; return o;
  }));
  const total = src.groups.reduce((n, g) => n + g.tiles.length, 0);
  const when = src.note && src.kind === "github" ? " · published " + new Date(src.note).toLocaleDateString() : "";
  $("sub").textContent = src.title + " · " + total + " picture" + (total === 1 ? "" : "s") + when;

  if (state.group !== "all" && !src.groups.some((g) => g.key === state.group)) state.group = "all";
  const chips = $("chips");
  chips.replaceChildren();
  const chip = (key, label, count) => {
    const c = el("button", { class: "chip", "aria-pressed": String(state.group === key) }, label, el("span", { text: String(count) }));
    c.onclick = () => { state.group = key; render(); };
    chips.append(c);
  };
  chip("all", "All", total);
  for (const g of src.groups) chip(g.key, g.title.replace(/ \(.*\)$/, ""), g.tiles.length);

  shown = [];
  for (const g of src.groups) {
    if (state.group !== "all" && g.key !== state.group) continue;
    const tiles = g.tiles.filter(matches);
    if (!tiles.length) continue;
    const grid = el("div", { class: "grid" });
    for (const t of tiles) {
      const i = shown.push(t) - 1;
      const img = el("img", { src: t.photo, alt: t.title, loading: "lazy", decoding: "async" });
      const b = el("button", { class: "tile", title: t.title },
        el("div", { class: "shot" }, img), el("div", { class: "cap" }, el("b", { text: t.title }), el("span", { text: t.sub })));
      b.onclick = () => openBig(i);
      grid.append(b);
    }
    main.append(el("section", {}, el("h2", {}, g.title, el("small", { text: String(tiles.length) })), grid));
  }
  if (!shown.length) main.append(el("div", { class: "empty" }, el("h2", { text: "Nothing matches “" + state.q + "”" })));
}

function openBig(i) {
  current = (i + shown.length) % shown.length;
  const t = shown[current];
  $("lb-img").src = t.photo; $("lb-img").alt = t.title;
  $("lb-title").textContent = t.title;
  $("lb-sys").textContent = t.sub;
  $("lb-details").textContent = t.details.join("  ·  ");
  $("lb-count").textContent = (current + 1) + " of " + shown.length;
  $("lb-open").href = t.photo;
  $("lb").classList.add("open");
  $("lb-close").focus();
}
function closeBig() { $("lb").classList.remove("open"); current = -1; }

async function getLatest() {
  try { await post("/api/get-latest"); pollSoon(); } catch (e) { showError(e.message); }
}

function showError(msg) {
  $("job").hidden = false; $("job-msg").textContent = "Couldn't start";
  $("job-err").hidden = false; $("job-err").textContent = msg; $("job-bar").hidden = true;
}

async function poll() {
  const s = await (await fetch("/api/status")).json();
  if (s.kind && (s.running || wasRunning || s.error)) {
    $("job").hidden = false;
    $("job-msg").textContent = s.message;
    const bar = $("job-bar");
    bar.hidden = !s.running;
    bar.classList.toggle("busy", s.running && s.progress == null);
    $("job-fill").style.width = s.progress == null ? "" : Math.round(s.progress * 100) + "%";
    $("job-err").hidden = !s.error; $("job-err").textContent = s.error;
    $("job-log-box").hidden = !s.log.length; $("job-log").textContent = s.log.join("\n");
  }
  $("get").disabled = $("shoot").disabled = s.running;
  if (wasRunning && !s.running) {
    await loadLibrary();
    if (s.kind === "capture") { const mac = lib.sources.find((x) => x.kind === "this-mac"); if (mac) { state.source = mac.id; render(); } }
    if (s.kind === "download") { state.source = "github"; render(); }
  }
  if (wasRunning && !s.running && !s.error) setTimeout(() => { $("job").hidden = true; }, 6000);
  wasRunning = s.running;
  if (s.running) setTimeout(poll, 800);
}
function pollSoon() { wasRunning = true; setTimeout(poll, 200); }

$("get").onclick = getLatest;
$("shoot").onclick = () => $("shoot-dialog").showModal();
$("shoot-cancel").onclick = () => $("shoot-dialog").close();
$("shoot-go").onclick = async () => {
  $("shoot-dialog").close();
  try { await post("/api/capture", { simulators: $("opt-sim").checked, screen: $("opt-screen").checked }); pollSoon(); }
  catch (e) { showError(e.message); }
};
$("source").onchange = (e) => { state.source = e.target.value; store.set("source", state.source); state.group = "all"; render(); };
$("q").oninput = (e) => { state.q = e.target.value; render(); };
$("lb-prev").onclick = () => openBig(current - 1);
$("lb-next").onclick = () => openBig(current + 1);
$("lb-close").onclick = closeBig;
$("lb-stage").onclick = (e) => { if (e.target === $("lb-stage")) closeBig(); };
document.addEventListener("keydown", (e) => {
  if (current < 0) return;
  if (e.key === "Escape") closeBig();
  else if (e.key === "ArrowLeft") openBig(current - 1);
  else if (e.key === "ArrowRight") openBig(current + 1);
});

loadLibrary().then(poll);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
