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
  echo "Xcode: $(xcodebuild -version 2>/dev/null | head -1 || echo none)"
} | tee "$OUT_DIR/$NAME-version.txt"

# Hide open windows so the desktop shows, then capture the whole screen.
osascript -e 'tell application "System Events" to set visible of every process whose visible is true and name is not "Finder" to false' 2>/dev/null || true
sleep 2
screencapture -x "$OUT_DIR/$NAME.png"
echo "Saved $OUT_DIR/$NAME.png"
