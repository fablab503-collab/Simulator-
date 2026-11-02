#!/bin/bash
# Double-click this in Finder to open the Gimmich Viewer (see scripts/gimmich-viewer.py).
# It opens a page in your browser; close this Terminal window to stop it.
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null || ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
  echo "The Gimmich Viewer needs Python 3.9 or newer."
  echo "On a Mac, install Xcode from the App Store (or run: xcode-select --install), then try again."
  read -r -p "Press Return to close." _
  exit 1
fi
exec python3 scripts/gimmich-viewer.py "$@"
