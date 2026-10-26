#!/usr/bin/env bash
# Builds and tests one project that detect-project.py found, and writes what
# happened to <out-dir>/result.txt (plus build.log and test.log). Works on
# Linux, macOS and Windows (in Git Bash, which GitHub's Windows machines have).
#
# Usage: build-project.sh <repo-folder> <project-json> <out-dir>
#   <project-json> is one entry of the plan's "projects" list.
set -uo pipefail

REPO="$(cd "$1" && pwd)"
PROJECT="$2"
OUT="$(mkdir -p "$3" && cd "$3" && pwd)"
# A Python that really runs (on Windows "python3" can be a store shortcut).
for PY in python3 python ""; do [[ -n "$PY" ]] && "$PY" -c "" 2>/dev/null && break; done

field() { "$PY" -c 'import json, sys; print(json.loads(sys.argv[1]).get(sys.argv[2], ""))' "$PROJECT" "$1"; }
KIND="$(field kind)"
DIR="$REPO/$(field path)"
BUILD="$(field build)"
TEST="$(field test)"

note() { echo "$*" | tee -a "$OUT/result.txt"; }
touch "$OUT/.started"   # anything newer than this was made by the build
note "Project: $(field repo) $(field path | sed 's#^\.$##')"
note "Kind: $KIND"
note "On: $(uname -s) $(uname -m)"
cd "$DIR"

# Apple apps: build the first scheme for the iPhone simulator, no signing needed.
xcodebuild_auto() {
  local proj="$1" flag="-project"
  [[ "$proj" == *.xcworkspace ]] && flag="-workspace"
  local scheme
  scheme="$(xcodebuild -list -json $flag "$proj" | "$PY" -c 'import json, sys
d = json.load(sys.stdin); d = d.get("project") or d.get("workspace") or {}
print((d.get("schemes") or [""])[0])')"
  note "Xcode scheme: $scheme"
  xcodebuild $flag "$proj" -scheme "$scheme" -sdk iphonesimulator \
    -destination 'generic/platform=iOS Simulator' -derivedDataPath "$OUT/dd" \
    CODE_SIGNING_ALLOWED=NO build
}

# Python projects get their own clean Python, so they can't clash with the
# machine's (or each other's) packages.
if [[ "$KIND" == Python ]]; then
  "$PY" -m venv "$OUT/venv"
  for bin in "$OUT/venv/bin" "$OUT/venv/Scripts"; do [[ -d "$bin" ]] && export PATH="$bin:$PATH"; done
  python -m pip install -q --upgrade pip setuptools wheel > /dev/null 2>&1
fi

result=success
if [[ -n "$BUILD" ]]; then
  [[ -f gradlew ]] && chmod +x gradlew
  start=$(date +%s)
  case "$BUILD" in
    xcodebuild-auto\ *) xcodebuild_auto "${BUILD#xcodebuild-auto }" > "$OUT/build.log" 2>&1 ;;
    *) bash -c "$BUILD" > "$OUT/build.log" 2>&1 ;;
  esac
  status=$?
  if [[ $status -eq 0 ]]; then
    note "Build: ok ($(( $(date +%s) - start )) s): $BUILD"
  else
    note "Build: FAILED (exit $status): $BUILD"
    tail -n 15 "$OUT/build.log" | sed 's/^/  | /' | tee -a "$OUT/result.txt"
    result=failed
  fi
fi

# Tests only count as information: a project's own tests can need things
# (servers, screens, secrets) that a fresh machine doesn't have.
if [[ "$result" == success && -n "$TEST" ]]; then
  if bash -c "$TEST" > "$OUT/test.log" 2>&1; then
    note "Tests: passed"
  else
    note "Tests: some failed (see test.log)"
  fi
fi

# What the build made: programs, apps and packages, newest first.
made="$(find . -type f \( -name '*.apk' -o -name '*.exe' -o -name '*.dll' -o -name '*.jar' -o -name '*.whl' \
          -o -name '*.so' -o -name '*.dylib' -o -perm -u+x \) -newer "$OUT/.started" \
          ! -path './.git/*' ! -path '*/node_modules/*' ! -path '*/build/*/build-script-*' ! -path '*/deps/*' ! -name '*.sh' ! -name '*.py' 2>/dev/null | head -8)"
apps="$(find "$OUT/dd" -name '*.app' -path '*iphonesimulator*' -maxdepth 6 2>/dev/null | head -1)"
[[ -n "$made" ]] && note "Made: $(echo "$made" | sed 's#^\./##' | tr '\n' ' ')"
[[ -n "$apps" ]] && note "Made: $(basename "$apps") (iPhone simulator app)" && echo "$apps" > "$OUT/ios-app.txt"
note "Result: $result"
[[ "$result" == success ]]
