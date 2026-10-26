#!/usr/bin/env bash
# Opens the Gimmich app pages (Studio, Camera, Connect a device) in Safari on the newest
# iPhone and iPad simulators and takes a screenshot of each. The Apple Watch has no web
# browser, so only its home screen is captured.
#
# Usage: gimmich-on-ios.sh OUT_DIR BASE_URL      (BASE_URL e.g. http://localhost:8080)
set -euo pipefail

OUT_DIR="${1:-gimmich-ios}"
BASE="${2:-http://localhost:8080}"
mkdir -p "$OUT_DIR"
DEVICES_JSON="$(xcrun simctl list devices available -j)"

# Prints "<udid><TAB><name>" for the first device whose name starts with PREFIX,
# using the newest installed runtime for OS (iOS, watchOS, ...).
pick_device() {
  local os="$1" prefix="$2"
  jq -r --arg os "$os" --arg prefix "$prefix" '
    [ .devices | to_entries
      | map(select(.key | test("SimRuntime\\." + $os + "-")))
      | sort_by(.key | split("-")[1:] | map(tonumber))
      | reverse[]
      | .value[]
      | select(.name | startswith($prefix)) ]
    | (first // empty)
    | "\(.udid)\t\(.name)"
  ' <<< "$DEVICES_JSON"
}

try_app() {
  local label="$1" os="$2" prefix="$3" line udid name
  line="$(pick_device "$os" "$prefix")"
  if [[ -z "$line" ]]; then
    echo "::warning::No $label simulator installed ($os runtime missing), skipping."
    return 0
  fi
  udid="${line%%$'\t'*}"
  name="${line#*$'\t'}"
  echo "==> $label: $name"
  xcrun simctl boot "$udid" || true
  xcrun simctl bootstatus "$udid" -b
  xcrun simctl ui "$udid" appearance light || true
  sleep 8

  if [[ "$os" == "watchOS" ]]; then
    # watchOS has no Safari: nothing of Gimmich can open here, so just show that the watch runs
    xcrun simctl io "$udid" screenshot "$OUT_DIR/$label - $name - home (no web browser on watchOS).png"
  else
    for page in "studio/:1 Studio" "studio/connect/:2 Connect a device" "studio/camera/:3 Camera"; do
      local path="${page%%:*}" title="${page#*:}"
      xcrun simctl openurl "$udid" "$BASE/$path"
      sleep 12                                  # Safari opens and the page loads
      xcrun simctl io "$udid" screenshot "$OUT_DIR/$label - $name - $title.png"
    done
  fi
  xcrun simctl shutdown "$udid" || true
}

try_app "iPhone"      iOS     "iPhone"
try_app "iPad"        iOS     "iPad"
try_app "Apple Watch" watchOS "Apple Watch"

echo "Done. Screenshots are in $OUT_DIR/"
ls -la "$OUT_DIR"
