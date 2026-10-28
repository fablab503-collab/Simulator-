"""Gimmich gym coach: lets an AI use a screen by itself, one step at a time.

Each step: take a screenshot -> show it to the AI with the task -> the AI
answers with ONE action (click, type, key, scroll, wait, done) -> do it ->
check if the task is done. Every step is saved (screenshot + action), so each
run is also training data for later.

Usage:
  python3 agent.py --task click-install            one practice task (tasks.toml)
  python3 agent.py --all --screen x11              every practice task on a screen
  python3 agent.py --screen x11 --ask "Open the File menu"   any job, no automatic check
Options:
  --model qwen3-vl-4b      which AI (a name from models/models.toml); default
                           qwen3-vl-4b. "script:FILE" replays actions from a file
                           (one JSON action per line), for testing without an AI.
  --server URL             use a model server that is already running
  --out DIR                where to save the runs (default gym-runs)
Safety: at most the task's number of steps, and the AI may never type
commands that delete, format or shut down; the run stops instead.
"""
import argparse
import base64
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import tomllib
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gimmich_gym import open_screen  # noqa: E402

PORT = 8765
DANGER = re.compile(r"\brm\s+-|\bmkfs|\bformat\s+[a-z]:|\bdel\s+/|\bshutdown\b|\breboot\b|\bdd\s+if=|"
                    r":\(\)\s*\{|\bsudo\b|\bchmod\s+-R\b|\bdiskpart\b", re.I)

PROMPT = """You are using a computer screen to do a task. Look at the screenshot.
Task: {task}
{history}
Reply with exactly ONE action as JSON on one line, nothing else. Choose from:
{{"action": "click", "x": X, "y": Y}}   positions from 0 to 1000 (0,0 is top-left, 1000,1000 is bottom-right)
{{"action": "type", "text": "..."}}      type text where the cursor is
{{"action": "key", "key": "Enter"}}      Enter, Escape, Tab, Backspace, Up, Down, Home, Back
{{"action": "scroll", "direction": "down"}}
{{"action": "done"}}                     when the task is finished"""


# --- The AI ---------------------------------------------------------------

class Scripted:
    """Replays actions from a file: for testing the gym without an AI."""

    def __init__(self, path):
        self.actions = [l.strip() for l in open(path) if l.strip()]

    def ask(self, prompt, png):
        return self.actions.pop(0) if self.actions else '{"action": "done"}'


class ModelServer:
    """A Gimmich model running in llama.cpp's server (started here, or already running)."""

    def __init__(self, model, url=None):
        self.proc, self.url = None, url
        if not url:
            repo = os.path.dirname(HERE)
            models = os.environ.get("MODELS_DIR", os.path.expanduser("~/gimmich-models"))
            subprocess.run([sys.executable, os.path.join(repo, "get-model.py"), "get", model, "--dest", models],
                           check=True, stdout=sys.stderr)
            files = os.listdir(os.path.join(models, model))
            brain = next(f for f in files if f.endswith(".gguf") and "mmproj" not in f.lower())
            eyes = next(f for f in files if f.endswith(".gguf") and "mmproj" in f.lower())
            bin_dir = subprocess.run([os.path.join(repo, "get-llama.sh")], check=True,
                                     capture_output=True, text=True).stdout.strip()
            env = dict(os.environ, LD_LIBRARY_PATH=bin_dir + ":" + os.environ.get("LD_LIBRARY_PATH", ""))
            self.url = "http://127.0.0.1:8080"
            self.proc = subprocess.Popen(
                [os.path.join(bin_dir, "llama-server"), "-m", os.path.join(models, model, brain),
                 "--mmproj", os.path.join(models, model, eyes), "--port", "8080", "-c", "8192",
                 "--temp", "0"], env=env, stdout=open(os.path.join(models, model, "server.log"), "w"),
                stderr=subprocess.STDOUT)
        for _ in range(600):  # loading a model can take a few minutes
            try:
                with urllib.request.urlopen(self.url + "/health", timeout=5) as r:
                    if json.load(r).get("status") == "ok":
                        break
            except Exception:
                pass
            if self.proc and self.proc.poll() is not None:
                sys.exit("The model server stopped; see server.log")
            time.sleep(2)
        print("Model ready at", self.url, file=sys.stderr)

    def ask(self, prompt, png):
        body = {"messages": [{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode()}},
                    {"type": "text", "text": prompt}]}],
                # Some AIs (AutoGLM) think aloud before the action, so leave room.
                "temperature": 0, "max_tokens": 512}
        req = urllib.request.Request(self.url + "/v1/chat/completions", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=900) as r:
            return json.load(r)["choices"][0]["message"]["content"]

    def stop(self):
        if self.proc:
            self.proc.terminate()


# --- Reading the AI's answer ----------------------------------------------

def parse(answer):
    """Turns the AI's reply into an action dict. Accepts the JSON we asked for,
    and the click(x, y) / <point>x y</point> styles some models use."""
    for m in re.finditer(r"\{[^{}]*\}", answer):
        try:
            a = json.loads(m.group(0))
        except ValueError:
            continue
        if isinstance(a, dict) and ("action" in a or "type" in a):
            name = str(a.get("action") or a.get("type")).lower()
            a["action"] = {"tap": "click", "left_click": "click", "press": "key", "hotkey": "key",
                           "finished": "done", "finish": "done", "input": "type", "write": "type"}.get(name, name)
            # Positions written as one text, e.g. "x": "434,499" (UI-TARS does this).
            for key in ("x", "coordinate", "point", "position"):
                both = re.findall(r"\d+(?:\.\d+)?", str(a.get(key, ""))) if isinstance(a.get(key), str) else []
                if len(both) >= 2:
                    a["x"], a["y"] = float(both[0]), float(both[1])
            if a["action"] == "click" and "x" not in a:
                pos = a.get("coordinate") or a.get("point") or a.get("position")
                if isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    a["x"], a["y"] = pos[0], pos[1]
            return a
    # AutoGLM's own style: do(action="Tap", element=[x, y]), do(action="Type", text="...")
    m = re.search(r'do\(action="(\w+)"(.*?)\)\s*$', answer, re.S | re.M) or re.search(r'do\(action="(\w+)"(.*)', answer, re.S)
    if m:
        kind, rest = m.group(1).lower(), m.group(2)
        pos = re.search(r"\[\s*(\d+)\s*,\s*(\d+)\s*\]", rest)
        text = re.search(r'text="([^"]*)"', rest)
        if kind in ("tap", "click", "double tap", "long press") and pos:
            return {"action": "click", "x": float(pos.group(1)), "y": float(pos.group(2))}
        if kind == "type" and text:
            return {"action": "type", "text": text.group(1)}
        if kind in ("back", "home", "enter"):
            return {"action": "key", "key": kind.capitalize()}
        if kind == "swipe":
            return {"action": "scroll", "direction": "down"}
    if re.search(r'finish\(', answer):
        return {"action": "done"}
    m = re.search(r"click\D*?(\d+(?:\.\d+)?)\D+(\d+(?:\.\d+)?)", answer, re.I) or \
        re.search(r"<point>\s*(\d+)\s+(\d+)\s*</point>", answer)
    if m:
        return {"action": "click", "x": float(m.group(1)), "y": float(m.group(2))}
    if re.search(r"\bdone\b|\bfinished\b", answer, re.I):
        return {"action": "done"}
    return {"action": "unknown", "raw": answer[:200]}


# How each AI gives click positions. Most use 0-1000 (what the prompt asks for);
# UI-TARS was trained on pixels of the picture it is shown.
PIXEL_MODELS = ("ui-tars",)


def small_png(path, longest=1280):
    """The screenshot, made smaller for the AI (positions are 0-1000, so size doesn't matter)."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im.thumbnail((longest, longest))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue(), Image.open(path).size, im.size


# --- Practice tasks -------------------------------------------------------

def load_tasks():
    with open(os.path.join(HERE, "tasks.toml"), "rb") as f:
        return tomllib.load(f)


class PracticeRoom:
    """The practice web pages (practice-app.py) shown in a Chrome window on the x11 screen."""

    def __init__(self, out):
        self.events = os.path.join(out, "events.jsonl")
        self.server = subprocess.Popen([sys.executable, os.path.join(HERE, "practice-app.py"), str(PORT), self.events])
        self.chrome = None
        time.sleep(1)

    def open(self, page, display):
        if self.chrome:
            self.chrome.terminate()
            self.chrome.wait()
        open(self.events, "w").close()
        browser = os.environ.get("CHROME") or shutil.which("google-chrome") or shutil.which("chromium")
        self.chrome = subprocess.Popen(
            [browser, "--app=http://127.0.0.1:%d/%s" % (PORT, page), "--window-position=0,0",
             "--window-size=1280,800", "--user-data-dir=/tmp/gimmich-gym-chrome", "--no-first-run",
             "--no-default-browser-check", "--disable-features=Translate", "--no-sandbox", "--disable-gpu"],
            env=dict(os.environ, DISPLAY=display), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Wait until the window has really been drawn (the first start of Chrome is slow).
        from PIL import ImageGrab
        for _ in range(30):
            time.sleep(1)
            small = ImageGrab.grab(xdisplay=display).convert("L").resize((64, 40))
            if sum(small.histogram()[200:]) > 0.1 * 64 * 40:  # the white card is showing
                break
        time.sleep(1)

    def happened(self, want):
        for line in open(self.events):
            event = json.loads(line)
            if all(str(event.get(k)).lower() == str(v).lower() for k, v in want.items()):
                return True
        return False

    def close(self):
        for p in (self.chrome, self.server):
            if p:
                p.terminate()


def android_front(package):
    out = subprocess.run(["adb", "shell", "dumpsys", "window"], capture_output=True, text=True).stdout
    return any(package in l for l in out.splitlines() if "mCurrentFocus" in l or "mFocusedApp" in l)


# --- One run --------------------------------------------------------------

def run_task(name, task, screen, ai, out, room=None):
    folder = os.path.join(out, name)
    os.makedirs(folder, exist_ok=True)
    if screen.name == "x11" and task.get("open"):
        room.open(task["open"], screen.display)
    elif screen.name == "android":
        screen.key("Home")
        time.sleep(2)

    def passed():
        check = task.get("check")
        if not check:
            return False
        if screen.name == "x11":
            return room.happened(check)
        return android_front(check)

    history, result, start = [], "failed", time.time()
    log = open(os.path.join(folder, "steps.jsonl"), "w")
    for step in range(task.get("steps", 10)):
        shot = screen.screenshot(os.path.join(folder, "step-%02d.png" % step))
        png, (w, h), (sw, sh) = small_png(shot)
        pixels = any(m in getattr(ai, "label", "") for m in PIXEL_MODELS)
        prompt = PROMPT.format(task=task["task"], history=("Actions so far: " + "; ".join(history)) if history else "")
        t0 = time.time()
        answer = ai.ask(prompt, png)
        action = parse(answer)
        record = {"step": step, "screenshot": os.path.basename(shot), "screen_size": [w, h],
                  "answer": answer, "action": action, "think_seconds": round(time.time() - t0, 1)}
        kind = action["action"]
        try:
            if kind == "click":
                if pixels:   # positions on the smaller picture the AI saw
                    x, y = float(action["x"]) * w / sw, float(action["y"]) * h / sh
                else:        # 0-1000 of the screen
                    x, y = float(action["x"]) * w / 1000, float(action["y"]) * h / 1000
                record["pixels"] = [round(x), round(y)]
                screen.click(x, y)
            elif kind == "type":
                text = str(action.get("text", ""))
                if DANGER.search(text):
                    record["stopped"] = "the AI tried to type a dangerous command; needs a person's OK"
                    log.write(json.dumps(record) + "\n")
                    result = "stopped (unsafe)"
                    break
                screen.type(text)
            elif kind == "key":
                screen.key(str(action.get("key", "Enter")))
            elif kind == "scroll":
                screen.scroll(str(action.get("direction", "down")))
            elif kind == "wait":
                time.sleep(3)
        except Exception as e:  # a bad action (e.g. no x) counts as a wasted step
            record["error"] = str(e)
        history.append(json.dumps(action))
        time.sleep(2)
        record["done_after"] = passed()
        log.write(json.dumps(record) + "\n")
        log.flush()
        print("  %s step %d: %s -> %s" % (name, step, json.dumps(action), "done!" if record["done_after"] else "not yet"),
              file=sys.stderr)
        if record["done_after"]:
            result = "success"
            break
        if kind == "done":
            break
    final = screen.screenshot(os.path.join(folder, "result.png"))
    steps = len(history)
    with open(os.path.join(folder, "result.txt"), "w") as f:
        f.write("Task: %s\nScreen: %s\nAI: %s\nSteps: %d of %d\nTime: %d s\nResult: %s\n" % (
            task["task"], screen.name, getattr(ai, "label", "?"), steps, task.get("steps", 10),
            time.time() - start, result))
    print("%s: %s in %d step(s)" % (name, result, steps))
    return result == "success", final


def main():
    p = argparse.ArgumentParser(description="Gimmich gym coach")
    p.add_argument("--task")
    p.add_argument("--all", action="store_true")
    p.add_argument("--screen", default="x11")
    p.add_argument("--ask")
    p.add_argument("--steps", type=int, default=10)
    p.add_argument("--model", default="qwen3-vl-4b")
    p.add_argument("--server")
    p.add_argument("--out", default="gym-runs")
    a = p.parse_args()

    tasks = load_tasks()
    if a.ask:
        chosen = {"ask": {"screen": a.screen, "task": a.ask, "steps": a.steps}}
    elif a.task:
        chosen = {a.task: tasks[a.task]}
    elif a.all:
        chosen = {k: t for k, t in tasks.items() if t["screen"] == a.screen}
    else:
        sys.exit(__doc__)

    os.makedirs(a.out, exist_ok=True)
    ai = Scripted(a.model[7:]) if a.model.startswith("script:") else ModelServer(a.model, a.server)
    ai.label = a.model
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(1))
    room = PracticeRoom(a.out) if any(t["screen"] == "x11" for t in chosen.values()) else None
    wins = 0
    try:
        for name, task in chosen.items():
            screen = open_screen(task["screen"])
            ok, _ = run_task(name, task, screen, ai, a.out, room)
            wins += ok
    finally:
        if room:
            room.close()
        if hasattr(ai, "stop"):
            ai.stop()
    print("Score: %d of %d tasks" % (wins, len(chosen)))
    with open(os.path.join(a.out, "score.txt"), "w") as f:
        f.write("%s: %d of %d\n" % (a.model, wins, len(chosen)))


if __name__ == "__main__":
    main()
