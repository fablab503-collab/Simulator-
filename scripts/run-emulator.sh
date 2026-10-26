#!/usr/bin/env bash
# Starts one game console emulator on a virtual screen and takes screenshots.
# Only free, legal content is used: homebrew games and test programs that
# libretro hosts for its Content Downloader, and Sony's own free PS3 system
# software. No commercial games or BIOS files are downloaded.
#
# Usage: run-emulator.sh <console> <out-dir>
#   nes snes gb gba genesis ps1 psp gamecube   (RetroArch + a homebrew game)
#   ps2 ps3 ps4                                (the standalone emulator's own screen)
# Needs: xvfb, imagemagick, xdotool, retroarch, unzip, gh (for ps2/ps3/ps4).
set -euo pipefail

CONSOLE="$1"
OUT_DIR="$2"
WORK="${WORK_DIR:-$PWD/work}"
mkdir -p "$OUT_DIR" "$WORK"
export APPIMAGE_EXTRACT_AND_RUN=1   # run AppImages without FUSE

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

shot() { import -window root "$OUT_DIR/$1.png"; echo "Saved $1.png"; }

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

# Standalone PlayStation emulators, downloaded from their official releases.
case "$CONSOLE" in
  ps2)
    gh release download -R PCSX2/pcsx2 --pattern '*linux-appimage-x64-Qt.AppImage' -D "$WORK" --clobber
    app="$(ls "$WORK"/*.AppImage | head -1)"
    echo "ps2: PCSX2 $(basename "$app") (needs a BIOS from your own PS2 to play)" | tee "$OUT_DIR/version.txt"
    ;;
  ps3)
    gh release download -R RPCS3/rpcs3-binaries-linux --pattern '*.AppImage' -D "$WORK" --clobber
    app="$(ls "$WORK"/*.AppImage | head -1)"
    # Sony gives out the PS3 system software for free on its own website.
    fw="$(curl -fsSL https://www.playstation.com/en-us/support/hardware/ps3/system-software/ | grep -oE 'https?://[^"]*PS3UPDAT\.PUP' | head -1)"
    echo "ps3: RPCS3 $(basename "$app") + Sony PS3 system software ($fw)" | tee "$OUT_DIR/version.txt"
    curl -fL --retry 3 -o "$WORK/PS3UPDAT.PUP" "$fw"
    chmod +x "$app"
    timeout 600 "$app" --installfw "$WORK/PS3UPDAT.PUP" >"$OUT_DIR/firmware-install.log" 2>&1 || echo "Firmware install ended with $?"
    ;;
  ps4)
    gh release download -R shadps4-emu/shadPS4 --pattern '*linux-qt*' -D "$WORK" --clobber
    for z in "$WORK"/*.zip; do [[ -f "$z" ]] && unzip -o -q "$z" -d "$WORK"; done
    app="$(find "$WORK" -name '*.AppImage' | head -1)"
    echo "ps4: shadPS4 $(basename "$app") (needs files from your own PS4 to play)" | tee "$OUT_DIR/version.txt"
    ;;
esac
chmod +x "$app"
"$app" >"$OUT_DIR/emulator.log" 2>&1 &
sleep 40
shot "$CONSOLE"

# PS3: also try starting the PS3's own home menu (the XMB) from the system software.
if [[ "$CONSOLE" == ps3 ]]; then
  vsh="$(find "$HOME/.config/rpcs3" -path '*dev_flash/vsh/module/vsh.self' 2>/dev/null | head -1)"
  if [[ -n "$vsh" ]]; then
    pkill -f rpcs3 || true; sleep 3
    "$app" --no-gui "$vsh" >"$OUT_DIR/xmb.log" 2>&1 &
    sleep 150
    shot "ps3-xmb"
  else
    echo "PS3 home menu not found (system software did not install)"
  fi
fi
