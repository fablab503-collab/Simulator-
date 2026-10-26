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

# IOS_MAJOR picks an older iOS (e.g. 17) instead of the newest one. Apple
# Watch versions went 10 (with iOS 17), 11 (iOS 18), then jumped to 26.
IOS_MAJOR="${IOS_MAJOR:-}"
WATCH_MAJOR=""
if [[ -n "$IOS_MAJOR" ]]; then
  if (( IOS_MAJOR >= 26 )); then WATCH_MAJOR="$IOS_MAJOR"; else WATCH_MAJOR=$(( IOS_MAJOR - 7 )); fi
fi

# Prints "<udid><TAB><name><TAB><runtime>" for the first device whose name starts with
# PREFIX, using the newest installed runtime for OS (iOS, watchOS, ...),
# or the newest one of version MAJOR when that is given.
pick_device() {
  local os="$1" prefix="$2" major="${3:-}"
  jq -r --arg os "$os" --arg prefix "$prefix" --arg major "$major" '
    [ .devices | to_entries
      | map(select(.key | test("SimRuntime\\." + $os + "-" + (if $major == "" then "" else $major + "-" end))))
      | sort_by(.key | split("-")[1:] | map(tonumber))
      | reverse[]
      | .key as $runtime
      | .value[]
      | select(.name | startswith($prefix))
      | . + {runtime: $runtime} ]
    | (first // empty)
    | "\(.udid)\t\(.name)\t\(.runtime)"
  ' <<< "$DEVICES_JSON"
}

shoot() {
  local label="$1" os="$2" prefix="$3" major="${4:-}"
  local line udid name runtime version
  line="$(pick_device "$os" "$prefix" "$major")"
  if [[ -z "$line" ]]; then
    echo "::warning::No $label simulator installed ($os runtime missing), skipping."
    return 0
  fi
  IFS=$'\t' read -r udid name runtime <<< "$line"
  # "com.apple.CoreSimulator.SimRuntime.iOS-26-5" -> "iOS 26.5"
  version="$(sed -E 's/.*SimRuntime\.//; s/^xrOS/visionOS/; s/-/ /; s/-/./g' <<< "$runtime")"
  echo "$label - $name: $version" >> "$OUT_DIR/devices.txt"

  echo "==> $label: $name ($udid)"
  xcrun simctl boot "$udid" || true          # ignore "already booted"
  # Some GitHub Macs list a simulator whose files are missing ("cannot
  # determine the runtime bundle"); skip it instead of failing everything.
  if ! xcrun simctl bootstatus "$udid" -b; then
    echo "::warning::$label ($name) could not start on this machine, skipping."
    xcrun simctl shutdown "$udid" 2>/dev/null || true
    return 0
  fi
  sleep 10                                    # let the home screen settle
  # Devices with more than one screen (like a folding iPhone) need each
  # screen named; simctl lists them when the plain screenshot fails.
  local err="$OUT_DIR/.screenshot-error.txt"
  if ! xcrun simctl io "$udid" screenshot "$OUT_DIR/$label - $name.png" 2>"$err"; then
    local displays
    displays="$(grep -oE -- '--display=[0-9]+' "$err" | grep -oE '[0-9]+' || true)"
    if [[ -z "$displays" ]]; then
      # Some versions name no screens ("no 'default' display port"): try the
      # inside screen, and skip the device if that fails too.
      if ! xcrun simctl io "$udid" screenshot --display=internal "$OUT_DIR/$label - $name.png"; then
        cat "$err" >&2
        echo "::warning::$label ($name): could not take a screenshot, skipping."
      fi
      rm -f "$err"; xcrun simctl shutdown "$udid" || true
      return 0
    fi
    for d in $displays; do
      xcrun simctl io "$udid" screenshot --display="$d" "$OUT_DIR/$label - $name (screen $d).png"
    done
  fi
  rm -f "$err"
  xcrun simctl shutdown "$udid" || true
}

shoot "iPhone"      iOS     "iPhone"      "$IOS_MAJOR"
shoot "iPad"        iOS     "iPad"        "$IOS_MAJOR"
shoot "Apple Watch" watchOS "Apple Watch" "$WATCH_MAJOR"

echo "Done. Screenshots are in $OUT_DIR/"
ls -la "$OUT_DIR"
