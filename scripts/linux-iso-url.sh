#!/usr/bin/env bash
# Prints the download link of the newest live ISO for one Linux distro.
# The link is looked up fresh every run, so new releases are picked up
# automatically. Usage: linux-iso-url.sh <name>, where <name> is one of
#   ubuntu fedora debian mint arch opensuse popos omarchy        (newest Linux)
#   ubuntu-24.04 ... ubuntu-6.06 ubuntu-4.10                     (older Ubuntu)
#   reactos freedos haiku freebsd chromeos                       (other free systems)
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
  ubuntu-4.10)
    # The very first Ubuntu ("Warty Warthog", 2004) only came as a 32-bit live CD.
    echo "https://old-releases.ubuntu.com/releases/4.10/warty-release-live-i386.iso" ;;
  ubuntu-*)
    # An older Ubuntu: newest point release, from the current site or the archive.
    v="${1#ubuntu-}"
    iso="$(get "https://releases.ubuntu.com/$v/" 2>/dev/null | grep -oE "ubuntu-$v(\.[0-9]+)*-desktop-amd64\.iso" | sort -uV | tail -1 || true)"
    if [[ -n "$iso" ]]; then echo "https://releases.ubuntu.com/$v/$iso"; exit 0; fi
    best=""; bestdir=""
    for dir in $(get https://old-releases.ubuntu.com/releases/ | grep -oE "href=\"$v(\.[0-9]+)*/\"" | grep -oE "$v(\.[0-9]+)*" | sort -uV); do
      cand="$(get "https://old-releases.ubuntu.com/releases/$dir/" | grep -oE "ubuntu-$v(\.[0-9]+)*-desktop-amd64\.iso" | sort -uV | tail -1 || true)"
      if [[ -n "$cand" ]]; then best="$cand"; bestdir="$dir"; fi
    done
    [[ -n "$best" ]] || exit 1
    echo "https://old-releases.ubuntu.com/releases/$bestdir/$best" ;;
  reactos)
    # ReactOS: a free, open-source system that looks and works like Windows XP.
    v="$(get https://sourceforge.net/projects/reactos/files/ReactOS/ | grep -oE '/files/ReactOS/[0-9.]+/' | grep -oE '[0-9]+\.[0-9.]*[0-9]' | sort -uV | tail -1)"
    f="$(get "https://sourceforge.net/projects/reactos/files/ReactOS/$v/" | grep -oE "ReactOS-$v-i386\.zip" | head -1)"
    echo "https://sourceforge.net/projects/reactos/files/ReactOS/$v/$f/download" ;;
  freedos)
    get https://www.freedos.org/download/ | grep -oE 'https://download\.freedos\.org/[0-9.]+/FD[0-9]+-?LiveCD\.zip' | sort -uV | tail -1 ;;
  haiku)
    get https://www.haiku-os.org/get-haiku/ | grep -oE 'https://haiku-release\.cdn\.haiku-os\.org/[^"<> ]+-x86_64-anyboot\.iso' | sort -uV | tail -1 ;;
  freebsd)
    base=https://download.freebsd.org/releases/amd64/amd64/ISO-IMAGES
    v="$(newest_dir "$base/")"
    echo "$base/$v/FreeBSD-$v-RELEASE-amd64-disc1.iso" ;;
  chromeos)
    echo "https://dl.google.com/chromeos-flex/images/latest.bin.zip" ;;
  *)
    echo "Unknown system: $1" >&2; exit 2 ;;
esac
