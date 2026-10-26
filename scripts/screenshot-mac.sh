#!/usr/bin/env bash
# Takes a screenshot of the Mac desktop and saves which macOS version and
# chip (Apple M-series or Intel) this Mac has.
# Usage: screenshot-mac.sh <out-dir> <name>
set -euo pipefail

OUT_DIR="${1:-screenshots}"
NAME="${2:-mac}"
mkdir -p "$OUT_DIR"

arch="$(uname -m)"
case "$arch" in
  arm64)  chip="Apple $(sysctl -n machdep.cpu.brand_string 2>/dev/null | sed 's/^Apple //')" ;;
  x86_64) chip="Intel ($(sysctl -n machdep.cpu.brand_string 2>/dev/null))" ;;
  *)      chip="$arch" ;;
esac

{
  echo "macOS $(sw_vers -productVersion) (build $(sw_vers -buildVersion))"
  echo "Chip: $chip"
  echo "Xcode: $(xcodebuild -version 2>/dev/null | sed -n 1p)"
} | tee "$OUT_DIR/$NAME-version.txt"

# GitHub's Macs have a plain black desktop. Use this macOS version's own
# wallpaper when it's installed (e.g. "Sequoia" on macOS 15).
case "$(sw_vers -productVersion | cut -d. -f1)" in
  27) wall=27 ;; 26) wall=Tahoe ;; 15) wall=Sequoia ;; 14) wall=Sonoma ;; 13) wall=Ventura ;; *) wall="" ;;
esac
pic="$(ls "/System/Library/Desktop Pictures/"*"$wall"*.heic 2>/dev/null | head -1 || true)"
[[ -z "$pic" ]] && pic="$(ls "/System/Library/Desktop Pictures/"*.heic 2>/dev/null | head -1 || true)"
if [[ -n "$pic" ]]; then
  echo "Wallpaper: $pic"
  osascript -e "tell application \"System Events\" to tell every desktop to set picture to POSIX file \"$pic\"" || true
  sleep 3
fi

# Hide open windows so the desktop shows, then capture the whole screen.
osascript -e 'tell application "System Events" to set visible of every process whose visible is true and name is not "Finder" to false' 2>/dev/null || true
sleep 2
screencapture -x "$OUT_DIR/$NAME.png"
echo "Saved $OUT_DIR/$NAME.png"
