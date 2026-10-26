#!/usr/bin/env bash
# Starts one game console emulator on a virtual screen and takes screenshots.
# Only free, legal content is used: homebrew games and test programs that
# libretro hosts for its Content Downloader, and Sony's own free PS3 system
# software. No commercial games or BIOS files are downloaded.
#
# Usage: run-emulator.sh <console> <out-dir>
#   nes snes gb gba genesis ps1 psp gamecube   (RetroArch + a homebrew game)
#   ps2 ps3 ps4                                (the standalone emulator's own screen)
# Needs: xvfb, xdotool, python3-pil, unzip, and retroarch (retro consoles)
# or flatpak (ps2/ps3/ps4).
set -euo pipefail

CONSOLE="$1"
OUT_DIR="$2"
WORK="${WORK_DIR:-$PWD/work}"
mkdir -p "$OUT_DIR" "$WORK"

CORES=https://buildbot.libretro.com/nightly/linux/x86_64/latest
GAMES=https://buildbot.libretro.com/assets/cores

# console -> libretro core, folder on libretro's site, homebrew file
case "$CONSOLE" in
  nes)      core=fceumm;          dir="Nintendo - Nintendo Entertainment System";       game="Alter Ego.nes" ;;
  snes)     core=snes9x;          dir="Nintendo - Super Nintendo Entertainment System"; game="KeepingSNESalive.sfc" ;;
  gb)       core=gambatte;        dir="Nintendo - GameBoy";                             game="Deadeus.gb" ;;
  gba)      core=mgba;            dir="Nintendo - GameBoy Advance";                     game="Celeste Classic (v1.0).zip" ;;
  genesis)  core=genesis_plus_gx; dir="Sega - Mega Drive - Genesis";                    game="Break An Egg.md" ;;
  ps1)      core=pcsx_rearmed;    dir="Sony - PlayStation";                             game="240pTestSuitePS1-EMU.zip" ;;
  psp)      core=ppsspp;          dir="Sony - PlayStation Portable";                    game="Cube Test.zip" ;;
  gamecube) core=dolphin;         dir="Nintendo - GameCube - Wii";                      game="Super Methane Brothers.zip" ;;
  ps2|ps3|ps4) core="" ;;
  *) echo "Unknown console: $CONSOLE" >&2; exit 2 ;;
esac

urlencode() { python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1]))' "$1"; }

# A virtual screen for the emulator window.
export DISPLAY=:99
Xvfb :99 -screen 0 1280x800x24 >/dev/null 2>&1 &
sleep 3

shot() {
  python3 -c "from PIL import ImageGrab; ImageGrab.grab(xdisplay='$DISPLAY').save('$OUT_DIR/$1.png')"
  echo "Saved $1.png"
}

if [[ -n "$core" ]]; then
  curl -fsSL --retry 3 -o "$WORK/core.zip" "$CORES/${core}_libretro.so.zip"
  unzip -o -q "$WORK/core.zip" -d "$WORK"
  curl -fsSL --retry 3 -o "$WORK/$game" "$GAMES/$(urlencode "$dir")/$(urlencode "$game")"
  content="$WORK/$game"
  if [[ "$game" == *.zip ]]; then
    unzip -o -q "$content" -d "$WORK/game"
    # The game is the biggest file inside (skips readme files).
    content="$(find "$WORK/game" -type f ! -iname '*.txt' ! -iname '*.md' ! -iname '*.pdf' ! -iname '*.htm*' -printf '%s %p\n' | sort -n | tail -1 | cut -d' ' -f2-)"
  fi
  echo "$CONSOLE: RetroArch core $core, homebrew \"$(basename "$content")\" (from libretro)" | tee "$OUT_DIR/version.txt"

  cat > "$WORK/retroarch.cfg" <<'CFG'
video_driver = "gl"
audio_driver = "null"
video_fullscreen = "false"
video_windowed_fullscreen = "false"
pause_nonactive = "false"
menu_driver = "rgui"
CFG
  retroarch --config "$WORK/retroarch.cfg" -L "$WORK/${core}_libretro.so" "$content" >"$OUT_DIR/retroarch.log" 2>&1 &
  sleep 25
  shot "$CONSOLE-1"
  # Press Start/Enter once to get past a title screen.
  xdotool key Return || true
  sleep 15
  shot "$CONSOLE"
  exit 0
fi

# Standalone PlayStation emulators, installed from Flathub (the official
# Linux app store). Flathub builds bring every library they need.
case "$CONSOLE" in
  ps2) app_id=net.pcsx2.PCSX2;        note="needs a BIOS from your own PS2 to play" ;;
  ps3) app_id=net.rpcs3.RPCS3;        note="with Sony's free PS3 system software" ;;
  ps4) app_id=net.shadps4.shadPS4;    note="needs files from your own PS4 to play" ;;
esac
flatpak --user remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak --user install -y --noninteractive flathub "$app_id"
version="$(flatpak --user info "$app_id" | awk -F': *' '/Version/ {print $2; exit}')"
echo "$CONSOLE: $app_id $version from Flathub ($note)" | tee "$OUT_DIR/version.txt"
run() { flatpak --user run --filesystem="$WORK" "$app_id" "$@"; }

# RPCS3 asks "Do you wish to use this (Flatpak) build anyway?" before doing
# anything. Answer Yes (Alt+Y) for a while so it can carry on.
say_yes() { for _ in $(seq 1 "${1:-20}"); do xdotool key alt+y 2>/dev/null || true; sleep 3; done; }

if [[ "$CONSOLE" == ps3 ]]; then
  # Sony gives out the PS3 system software for free on its own website.
  fw="$(curl -fsSL https://www.playstation.com/en-us/support/hardware/ps3/system-software/ | grep -oE 'https?://[^"]*PS3UPDAT\.PUP' | head -1)"
  echo "PS3 system software: $fw" | tee -a "$OUT_DIR/version.txt"
  curl -fL --retry 3 -o "$WORK/PS3UPDAT.PUP" "$fw"
  say_yes 40 & yes_pid=$!
  timeout 900 flatpak --user run --filesystem="$WORK" "$app_id" --installfw "$WORK/PS3UPDAT.PUP" >"$OUT_DIR/firmware-install.log" 2>&1 || echo "Firmware install ended with $?"
  kill "$yes_pid" 2>/dev/null || true
fi

run >"$OUT_DIR/emulator.log" 2>&1 &
if [[ "$CONSOLE" == ps3 ]]; then say_yes 10 & fi
sleep 45
shot "$CONSOLE"

# PS3: also try starting the PS3's own home menu (the XMB) from the system software.
if [[ "$CONSOLE" == ps3 ]]; then
  vsh="$(find "$HOME/.var/app/$app_id" "$HOME/.config/rpcs3" -path '*dev_flash/vsh/module/vsh.self' 2>/dev/null | head -1 || true)"
  if [[ -n "$vsh" ]]; then
    pkill -f rpcs3 || true; sleep 3
    run --no-gui "$vsh" >"$OUT_DIR/xmb.log" 2>&1 &
    say_yes 10 &
    sleep 150
    shot "ps3-xmb"
  else
    echo "PS3 home menu not found (system software did not install)"
  fi
fi
