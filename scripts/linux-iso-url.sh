#!/usr/bin/env bash
# Prints the download link of the newest live ISO for one Linux distro.
# The link is looked up fresh every run, so new releases are picked up
# automatically. Usage: linux-iso-url.sh ubuntu|fedora|debian|mint|arch|opensuse|popos|omarchy
set -euo pipefail

get() { curl -fsSL --retry 3 "$1"; }
# Highest "NN.NN/" style folder in a directory listing.
newest_dir() { get "$1" | grep -oE 'href="[0-9]+(\.[0-9]+)*/"' | grep -oE '[0-9]+(\.[0-9]+)*' | sort -V | tail -1; }

case "${1:?distro name required}" in
  ubuntu)
    v="$(newest_dir https://releases.ubuntu.com/)"
    iso="$(get "https://releases.ubuntu.com/$v/SHA256SUMS" | grep -oE 'ubuntu-[0-9.]+-desktop-amd64\.iso' | head -1)"
    echo "https://releases.ubuntu.com/$v/$iso" ;;
  fedora)
    get https://fedoraproject.org/releases.json | jq -r '
      [ .[] | select(.variant == "Workstation" and .arch == "x86_64" and (.link | endswith(".iso")))
            | select(.version | test("^[0-9]+$")) ]
      | sort_by(.version | tonumber) | last | .link' ;;
  debian)
    base=https://cdimage.debian.org/debian-cd/current-live/amd64/iso-hybrid
    echo "$base/$(get "$base/SHA256SUMS" | grep -oE 'debian-live-[0-9.]+-amd64-gnome\.iso$' | head -1)" ;;
  mint)
    base=https://mirrors.edge.kernel.org/linuxmint/stable
    v="$(newest_dir "$base/")"
    echo "$base/$v/linuxmint-$v-cinnamon-64bit.iso" ;;
  arch)
    echo "https://geo.mirror.pkgbuild.com/iso/latest/archlinux-x86_64.iso" ;;
  opensuse)
    echo "https://download.opensuse.org/tumbleweed/iso/openSUSE-Tumbleweed-KDE-Live-x86_64-Current.iso" ;;
  popos)
    # Try newer Pop!_OS versions first; the API answers 404 for ones that don't exist yet.
    for v in 28.04 26.10 26.04 24.10 24.04; do
      if url="$(get "https://api.pop-os.org/builds/$v/intel" 2>/dev/null | jq -r '.url // empty')" && [[ -n "$url" ]]; then
        echo "$url"; exit 0
      fi
    done
    exit 1 ;;
  omarchy)
    get https://omarchy.org/ | grep -oE 'https://iso\.omarchy\.org/omarchy-[0-9.]+\.iso' | sort -uV | tail -1 ;;
  *)
    echo "Unknown distro: $1" >&2; exit 2 ;;
esac
