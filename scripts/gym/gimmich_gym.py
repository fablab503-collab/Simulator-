"""Gimmich gym: one set of "eyes and hands" for every system, so an AI (or a
script) can look at a screen and use it the same way everywhere.

Every screen has the same five commands:
  screenshot(path)          save what the screen shows as a PNG
  click(x, y)               click (tap) at a pixel
  type(text)                type text
  key(name)                 press a key: Enter, Escape, Tab, Backspace, Up,
                            Down, Left, Right, Home, Back (Android), Space
  scroll(direction)         scroll "up" or "down"

Screens so far:
  x11       a Linux screen (the real one or Xvfb): desktops, browsers, apps and
            every game emulator Gimmich runs. Needs xdotool and python3-pil.
  android   an Android phone or emulator, through adb.

Command line (handy for trying it by hand):
  python3 gimmich_gym.py x11 screenshot shot.png
  python3 gimmich_gym.py android click 540 1200
  python3 gimmich_gym.py x11 type "hello"
  python3 gimmich_gym.py x11 key Enter
"""
import os
import subprocess
import sys
import time


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


class X11:
    name = "x11"
    KEYS = {"Enter": "Return", "Backspace": "BackSpace", "Esc": "Escape", "Space": "space"}

    def __init__(self, display=None):
        self.display = display or os.environ.get("DISPLAY", ":99")
        self.env = dict(os.environ, DISPLAY=self.display)

    def screenshot(self, path):
        from PIL import ImageGrab
        ImageGrab.grab(xdisplay=self.display).save(path)
        return path

    def click(self, x, y):
        run(["xdotool", "mousemove", str(int(x)), str(int(y)), "click", "1"], env=self.env)

    def type(self, text):
        run(["xdotool", "type", "--delay", "40", "--", text], env=self.env)

    def key(self, name):
        run(["xdotool", "key", self.KEYS.get(name, name)], env=self.env)

    def scroll(self, direction):
        button = "4" if direction == "up" else "5"
        run(["xdotool", "click", "--repeat", "5", button], env=self.env)


class Android:
    name = "android"
    KEYS = {"Enter": "KEYCODE_ENTER", "Escape": "KEYCODE_BACK", "Back": "KEYCODE_BACK",
            "Home": "KEYCODE_HOME", "Tab": "KEYCODE_TAB", "Backspace": "KEYCODE_DEL",
            "Up": "KEYCODE_DPAD_UP", "Down": "KEYCODE_DPAD_DOWN", "Left": "KEYCODE_DPAD_LEFT",
            "Right": "KEYCODE_DPAD_RIGHT", "Space": "KEYCODE_SPACE"}

    def __init__(self, serial=None):
        self.adb = ["adb"] + (["-s", serial] if serial else [])

    def screenshot(self, path):
        with open(path, "wb") as f:
            run(self.adb + ["exec-out", "screencap", "-p"], stdout=f)
        return path

    def click(self, x, y):
        run(self.adb + ["shell", "input", "tap", str(int(x)), str(int(y))])

    def type(self, text):
        # "input text" needs spaces as %s and shell characters escaped.
        safe = "".join("\\" + c if c in "\\'\"`$&|;<>()*?!#~" else c for c in text).replace(" ", "%s")
        run(self.adb + ["shell", "input", "text", safe])

    def key(self, name):
        run(self.adb + ["shell", "input", "keyevent", self.KEYS.get(name, name)])

    def scroll(self, direction):
        # Swipe in the middle of a phone-sized screen.
        y1, y2 = ("1600", "600") if direction == "down" else ("600", "1600")
        run(self.adb + ["shell", "input", "swipe", "540", y1, "540", y2, "300"])


SCREENS = {"x11": X11, "android": Android}


def open_screen(name):
    if name not in SCREENS:
        sys.exit("Unknown screen %r (choose from %s)" % (name, ", ".join(SCREENS)))
    return SCREENS[name]()


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    screen, command, args = open_screen(sys.argv[1]), sys.argv[2], sys.argv[3:]
    if command == "screenshot":
        print(screen.screenshot(args[0] if args else "screen.png"))
    elif command == "click":
        screen.click(float(args[0]), float(args[1]))
    elif command == "type":
        screen.type(" ".join(args))
    elif command == "key":
        screen.key(args[0])
    elif command == "scroll":
        screen.scroll(args[0] if args else "down")
    else:
        sys.exit("Unknown command %r" % command)
    time.sleep(0.2)


if __name__ == "__main__":
    main()
