#!/usr/bin/env bash
# Opens one file on Linux the right way for its kind (see route-file.py) and
# saves what happened: a picture (result.png) and a short note (result.txt).
#
# Usage: run-file-linux.sh <file> <kind> <extra> <out-dir>
#   disc-image                  boots it in QEMU (boot-linux.sh)
#   game-rom                    plays it in RetroArch (run-emulator.sh)
#   web-page, ebook             opens it in headless Chrome
#   pdf                         draws the first page
#   video, audio, image         reads its details and draws a preview
#   code                        compiles/runs it and shows the output
#   text                        shows the first lines
#   linux-appimage/program      starts it on a virtual screen
#   linux-deb, linux-rpm, zip   lists what is inside
# Needs: python3-pil, and for some kinds xvfb, ffmpeg, poppler-utils, chrome,
# qemu (see run-file.yml).
set -euo pipefail

FILE="$(realpath "$1")"
KIND="$2"
EXTRA="$3"
OUT="$(mkdir -p "$4" && realpath "$4")"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${WORK_DIR:-$PWD/work}"
mkdir -p "$WORK"
NAME="$(basename "$FILE")"
CHROME="${CHROME:-google-chrome}"

note() { echo "$*" | tee -a "$OUT/result.txt"; }

# Draws text onto result.png (for results that are words, not pictures).
text_picture() {
  python3 - "$OUT/result.png" "$1" <<'PY'
import sys
from PIL import Image, ImageDraw, ImageFont
out, text_file = sys.argv[1:]
lines = open(text_file, errors="replace").read().splitlines()[:45] or ["(no output)"]
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 18)
except OSError:
    font = ImageFont.load_default()
im = Image.new("RGB", (1280, 40 + 24 * len(lines)), (22, 33, 46))
d = ImageDraw.Draw(im)
for i, line in enumerate(lines):
    d.text((20, 20 + 24 * i), line[:110], font=font, fill=(220, 230, 240))
im.save(out)
PY
}

# A virtual screen, for programs that open a window.
screen() {
  export DISPLAY=:98
  Xvfb :98 -screen 0 1280x800x24 >/dev/null 2>&1 &
  sleep 3
}
shot() { python3 -c "from PIL import ImageGrab; ImageGrab.grab(xdisplay=':98').save('$OUT/result.png')"; }

note "File: $NAME"
note "Kind: $KIND${EXTRA:+ ($EXTRA)}"

case "$KIND" in
  disc-image)
    MEDIA_FILE="$FILE" WORK_DIR="$WORK" "$HERE/boot-linux.sh" disc "$OUT/boot" 6
    cp "$OUT/boot/disc.png" "$OUT/result.png"
    note "Booted in QEMU for 6 minutes (photos every 30 s in boot/)"
    ;;

  game-rom)
    ROM_FILE="$FILE" WORK_DIR="$WORK" "$HERE/run-emulator.sh" "$EXTRA" "$OUT/game"
    cp "$OUT/game/$EXTRA.png" "$OUT/result.png"
    note "$(cat "$OUT/game/version.txt")"
    ;;

  web-page|ebook)
    page="$FILE"
    if [[ "$KIND" == ebook ]]; then
      # An EPUB is a zip of web pages: open the first chapter in its reading order.
      mkdir -p "$WORK/book" && unzip -o -q "$FILE" -d "$WORK/book"
      page="$(python3 - "$WORK/book" <<'PY'
import os, re, sys
root = sys.argv[1]
opf = re.search(r'full-path="([^"]+)"', open(os.path.join(root, "META-INF/container.xml")).read())[1]
text = open(os.path.join(root, opf)).read()
items = dict(re.findall(r'<item\b[^>]*?id="([^"]+)"[^>]*?href="([^"]+)"', text))
items.update({i: h for h, i in re.findall(r'<item\b[^>]*?href="([^"]+)"[^>]*?id="([^"]+)"', text)})
first = re.search(r'<itemref\b[^>]*idref="([^"]+)"', text)[1]
print(os.path.join(root, os.path.dirname(opf), items[first]))
PY
)"
      note "First chapter: ${page#"$WORK/book/"}"
      # Chapters are XHTML; Chrome is more forgiving with them read as HTML.
      cp "$page" "${page%.*}.gimmich.html"; page="${page%.*}.gimmich.html"
    elif [[ "$page" != *.htm* ]]; then
      # Chrome only shows local files as pages when their name says so.
      cp "$FILE" "$WORK/page.html"; page="$WORK/page.html"
    fi
    timeout -k 10 90 "$CHROME" --headless=new --no-sandbox --disable-gpu --hide-scrollbars \
      --window-size=1280,800 --virtual-time-budget=5000 \
      --screenshot="$OUT/result.png" "file://$page" 2>"$OUT/chrome.log"
    note "Opened in headless Chrome ($("$CHROME" --version))"
    ;;

  pdf)
    pdfinfo "$FILE" > "$OUT/pdfinfo.txt" || true
    pdftoppm -png -r 80 -f 1 -l 1 -singlefile "$FILE" "$OUT/result"
    note "Pages: $(awk '/^Pages:/ {print $2}' "$OUT/pdfinfo.txt")"
    ;;

  video)
    ffprobe -v error -show_entries format=duration:stream=codec_name,width,height \
      -of default=nw=1 "$FILE" | tee "$OUT/details.txt"
    # Nine frames from across the video, in a 3x3 grid.
    length="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$FILE")"
    ffmpeg -v error -y -i "$FILE" -vf "fps=9/$length,scale=426:-1,tile=3x3" \
      -frames:v 1 "$OUT/result.png"
    note "Preview: 9 frames from across the video"
    ;;

  audio)
    ffprobe -v error -show_entries format=duration:stream=codec_name,sample_rate,channels \
      -of default=nw=1 "$FILE" | tee "$OUT/details.txt"
    ffmpeg -v error -y -i "$FILE" -filter_complex "showwavespic=s=1280x400" -frames:v 1 "$OUT/result.png"
    note "Preview: the sound wave"
    ;;

  image)
    python3 -c "
import sys
from PIL import Image
im = Image.open(sys.argv[1]); print('Size: %dx%d, format %s' % (im.width, im.height, im.format))
im.convert('RGB').save(sys.argv[2])" "$FILE" "$OUT/result.png" | tee -a "$OUT/result.txt"
    ;;

  code)
    cd "$WORK"
    cp "$FILE" .
    status=0
    build() { timeout 300 "$@" > "$OUT/build.txt" 2>&1 || status=$?; }
    case "$EXTRA" in
      python)     cmd=(python3 "$NAME") ;;
      javascript) cmd=(node "$NAME") ;;
      shell)      cmd=(bash "$NAME") ;;
      java)       cmd=(java "$NAME") ;;
      go)         cmd=(go run "$NAME") ;;
      rust)       build rustc -O -o prog "$NAME"; cmd=(./prog) ;;
      c)          build gcc -O2 -o prog "$NAME" -lm; cmd=(./prog) ;;
      cpp)        build g++ -O2 -o prog "$NAME"; cmd=(./prog) ;;
    esac
    if [[ "$status" -ne 0 ]]; then
      { echo "Could not compile $NAME:"; cat "$OUT/build.txt"; } > "$WORK/shown.txt"
      note "Ran as $EXTRA: did not compile (errors in build.txt)"
    else
      # Every program gets 60 seconds.
      timeout 60 "${cmd[@]}" > "$OUT/output.txt" 2>&1 || status=$?
      { echo "\$ ${cmd[*]}"; cat "$OUT/output.txt"; echo; echo "(exit code $status)"; } > "$WORK/shown.txt"
      note "Ran as $EXTRA, exit code $status (output in output.txt)"
    fi
    text_picture "$WORK/shown.txt"
    ;;

  text)
    text_picture "$FILE"
    note "Lines: $(wc -l < "$FILE")"
    ;;

  linux-appimage|linux-program)
    screen
    chmod +x "$FILE"
    # AppImages normally mount themselves with FUSE; extracting works everywhere.
    APPIMAGE_EXTRACT_AND_RUN=1 timeout 60 "$FILE" > "$OUT/output.txt" 2>&1 &
    sleep 30
    shot
    note "Started on a virtual screen; picture taken after 30 s (output in output.txt)"
    ;;

  linux-deb)
    dpkg-deb --info "$FILE" > "$WORK/shown.txt"
    dpkg-deb --contents "$FILE" | head -30 >> "$WORK/shown.txt"
    cp "$WORK/shown.txt" "$OUT/details.txt"
    text_picture "$WORK/shown.txt"
    note "Package: $(dpkg-deb --field "$FILE" Package Version | tr '\n' ' ')"
    ;;

  linux-rpm)
    { rpm -qip "$FILE"; rpm -qlp "$FILE" | head -30; } > "$WORK/shown.txt" 2>&1 || true
    cp "$WORK/shown.txt" "$OUT/details.txt"
    text_picture "$WORK/shown.txt"
    ;;

  zip)
    unzip -l "$FILE" | head -45 > "$WORK/shown.txt"
    cp "$WORK/shown.txt" "$OUT/details.txt"
    text_picture "$WORK/shown.txt"
    note "Listed what is inside the zip"
    ;;

  *)
    { file "$FILE"; echo; xxd "$FILE" | head -30; } > "$WORK/shown.txt"
    text_picture "$WORK/shown.txt"
    note "Not a kind Gimmich knows yet: showing its first bytes"
    ;;
esac

echo "Saved the result to $OUT"
