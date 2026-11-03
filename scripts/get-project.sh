#!/usr/bin/env bash
# Downloads one GitHub project for Gimmich (only the newest version of it).
#
# For private projects, the GIMMICH_GITHUB_TOKEN secret (in $TOKEN) is handed
# to git for this one download only. It is never saved in the project's
# folder, so the project's own build and test commands can't read it.
#
# Usage: get-project.sh <owner/repo> <folder>
# Settings: TOKEN (optional, for private projects), REF (optional branch or tag)
set -euo pipefail

slug="$1"
[[ "$slug" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || { echo "::error::Not a GitHub repository: $slug" >&2; exit 1; }

if [[ -n "${TOKEN:-}" ]]; then
  # Settings given this way only live as long as this script: git writes
  # nothing to the project's .git/config (a token in the link would be saved there).
  login="$(printf 'x-access-token:%s' "$TOKEN" | base64 | tr -d '\n')"
  export GIT_CONFIG_COUNT=1
  export GIT_CONFIG_KEY_0="http.https://github.com/.extraheader"
  export GIT_CONFIG_VALUE_0="AUTHORIZATION: basic $login"
fi
git clone -q --depth 1 ${REF:+--branch "$REF"} "https://github.com/$slug" "$2"
