#!/usr/bin/env bash
# Downloads the newest live ISO of one system (Linux, older Ubuntu, ReactOS,
# FreeDOS, Haiku, FreeBSD, ChromeOS Flex), boots it in a QEMU virtual
# machine, and saves a screenshot every 30 seconds.
# Usage: boot-linux.sh <system> <out-dir> [minutes]
# Needs: qemu-system-x86, ovmf, python3-pil, unzip (and /dev/kvm for speed).
set -euo pipefail

DISTRO="$1"
OUT_DIR="$2"
MINUTES="${3:-8}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${WORK_DIR:-$PWD/work}"
mkdir -p "$OUT_DIR" "$WORK"

URL="$("$HERE/linux-iso-url.sh" "$DISTRO")"
FILE="$(basename "${URL%/download}")"   # SourceForge links end in /download
MEDIA="$WORK/$FILE"
echo "Newest $DISTRO: $URL"
echo "$DISTRO: $FILE" > "$OUT_DIR/version.txt"
# Big downloads sometimes break halfway: retry any error and resume where it stopped.
[[ -f "$MEDIA" ]] || curl -fL --http1.1 --retry 8 --retry-delay 10 --retry-all-errors -C - -o "$MEDIA" "$URL"

# Some systems come zipped: use the CD image (or ChromeOS's disk image) inside,
# preferring a "live" CD when there is more than one.
if [[ "$MEDIA" == *.zip ]]; then
  unzip -o -q "$MEDIA" -d "$WORK/unzipped"
  MEDIA="$(find "$WORK/unzipped" -type f \( -iname '*live*.iso' -o -iname '*.iso' -o -iname '*.bin' \) | sort | awk 'tolower($0) ~ /live/ {print; found=1; exit} {first = first ? first : $0} END {if (!found) print first}')"
  echo "Using $(basename "$MEDIA") from the zip"
  echo "$DISTRO: $(basename "$MEDIA")" > "$OUT_DIR/version.txt"
fi

MON="$WORK/monitor.sock"
rm -f "$MON"

# Old systems (2000s Ubuntu, ReactOS, FreeDOS, Haiku) need an old-style PC:
# BIOS startup, IDE CD drive and a standard VGA screen. Newer ones get UEFI.
case "$DISTRO" in
  ubuntu-4.10)
    # 2004's kernel freezes on modern virtual CPUs: fully emulate an old
    # Pentium III instead (slower, so give it 20 minutes).
    MACHINE=(-machine pc,accel=tcg -cpu pentium3 -smp 1 -m 512 -vga cirrus
             -nic user,model=ne2k_pci)
    MINUTES="${3:-20}"
    ;;
  ubuntu-6.06|ubuntu-8.04)
    # 2004-2008: also an older graphics card (Cirrus) their drivers know, and
    # more time, because they start slowly.
    MACHINE=(-machine pc,accel=kvm:tcg -cpu qemu64 -smp 1 -m 1024 -vga cirrus
             -nic user,model=e1000)
    MINUTES="${3:-14}"
    ;;
  ubuntu-10.04|ubuntu-12.04|ubuntu-14.04|reactos|freedos|haiku)
    MACHINE=(-machine pc,accel=kvm:tcg -cpu qemu64 -smp 2 -m 2048 -vga std
             -nic user,model=e1000)
    ;;
  chromeos)
    # ChromeOS Flex expects to start from a USB stick; with virtio graphics
    # it reaches its logo (the plain VGA screen stayed on the firmware).
    cp /usr/share/OVMF/OVMF_VARS_4M.fd "$WORK/vars.fd"
    MACHINE=(-machine q35,accel=kvm:tcg -cpu max -smp 4 -m 6144
             -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd
             -drive if=pflash,format=raw,file="$WORK/vars.fd"
             -device virtio-vga -netdev user,id=n0 -device virtio-net-pci,netdev=n0)
    MINUTES="${3:-12}"
    ;;
  *)
    cp /usr/share/OVMF/OVMF_VARS_4M.fd "$WORK/vars.fd"
    MACHINE=(-machine q35,accel=kvm:tcg -cpu max -smp 4 -m 6144
             -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd
             -drive if=pflash,format=raw,file="$WORK/vars.fd"
             -device virtio-vga -netdev user,id=n0 -device virtio-net-pci,netdev=n0)
    ;;
esac

# ChromeOS Flex is a disk image (a USB stick), not a CD.
if [[ "$MEDIA" == *.bin ]]; then
  DISK=(-drive file="$MEDIA",format=raw,if=none,id=usbstick
        -device qemu-xhci -device usb-storage,drive=usbstick,bootindex=0)
else
  DISK=(-cdrom "$MEDIA" -boot d)
fi

qemu-system-x86_64 "${MACHINE[@]}" "${DISK[@]}" \
  -display none \
  -monitor unix:"$MON",server,nowait \
  -daemonize -pidfile "$WORK/qemu.pid"

mon() { python3 "$HERE/qemu-monitor.py" "$MON" "$@"; }
for _ in $(seq 1 30); do [[ -S "$MON" ]] && break; sleep 1; done

# Pick the "start live system" entry in the boot menu. Fedora's default
# entry checks the disc first (slow), so move up to "Start Fedora". Older
# Ubuntu CDs first ask for a language, then show their menu: Enter 3 times.
sleep 12
case "$DISTRO" in
  fedora)    mon "sendkey up" "sendkey ret" ;;
  ubuntu-*)  mon "sendkey ret"; sleep 3; mon "sendkey ret"; sleep 3; mon "sendkey ret" ;;
  *)         mon "sendkey ret" ;;
esac

shots=$(( MINUTES * 2 ))
for i in $(seq 1 "$shots"); do
  sleep 30
  n=$(printf '%02d' "$i")
  # Nudge the mouse and tap Shift so the screen doesn't go to sleep or lock
  # (KDE ignores mouse nudges, but counts a key press as activity).
  # Ubuntu 8.04 shows a harmless "settings daemon" error popup: Escape closes it.
  [[ "$DISTRO" == ubuntu-8.04 ]] && mon "sendkey esc"
  mon "mouse_move 5 5" "mouse_move -5 -5" "sendkey shift" "screendump $WORK/$DISTRO-$n.ppm"
done
sleep 1

# QEMU saves PPM images; turn them into PNG. The main photo is the last one
# that isn't a blank screen (like "Display output is not active").
python3 - "$WORK" "$OUT_DIR" "$DISTRO" <<'PY'
import glob, os, shutil, sys
from PIL import Image
work, out, distro = sys.argv[1:]
def blank(im):
    small = im.convert("L").resize((320, 200))
    lit = sum(small.histogram()[41:])
    return lit < 0.005 * 320 * 200
pngs, good = [], []
for ppm in sorted(glob.glob(os.path.join(work, distro + "-*.ppm"))):
    png = os.path.join(out, os.path.basename(ppm)[:-4] + ".png")
    im = Image.open(ppm)
    im.save(png)
    pngs.append(png)
    if not blank(im):
        good.append(png)
main = (good or pngs)[-1:]
if main:
    shutil.copy(main[0], os.path.join(out, distro + ".png"))
print("Converted", len(pngs), "screenshots;", len(good), "show something; main photo:", main)
PY

kill "$(cat "$WORK/qemu.pid")" 2>/dev/null || true
echo "Saved $shots screenshots to $OUT_DIR"
