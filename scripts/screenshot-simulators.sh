#!/usr/bin/env bash
# Boots the newest iPhone, iPad and Apple Watch simulators that are
# installed on this Mac, takes a screenshot of each, then shuts them down.
# Works on any Mac with Xcode, and on GitHub's macOS runners.
set -euo pipefail

OUT_DIR="${1:-screenshots}"
mkdir -p "$OUT_DIR"

# Save what is installed, so you can see it in the results.
xcrun simctl list runtimes > "$OUT_DIR/installed-runtimes.txt"
xcrun simctl list devices available > "$OUT_DIR/available-devices.txt"

DEVICES_JSON="$(xcrun simctl list devices available -j)"

# Prints "<udid><TAB><name>" for the first device whose name starts with
# PREFIX, using the newest installed runtime for OS (iOS, watchOS, ...).
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

shoot() {
  local label="$1" os="$2" prefix="$3"
  local line udid name
  line="$(pick_device "$os" "$prefix")"
  if [[ -z "$line" ]]; then
    echo "::warning::No $label simulator installed ($os runtime missing), skipping."
    return 0
  fi
  udid="${line%%$'\t'*}"
  name="${line#*$'\t'}"

  echo "==> $label: $name ($udid)"
  xcrun simctl boot "$udid" || true          # ignore "already booted"
  xcrun simctl bootstatus "$udid" -b
  sleep 10                                    # let the home screen settle
  xcrun simctl io "$udid" screenshot "$OUT_DIR/$label - $name.png"
  xcrun simctl shutdown "$udid" || true
}

shoot "iPhone"      iOS     "iPhone"
shoot "iPad"        iOS     "iPad"
shoot "Apple Watch" watchOS "Apple Watch"

echo "Done. Screenshots are in $OUT_DIR/"
ls -la "$OUT_DIR"
