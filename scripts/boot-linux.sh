#!/usr/bin/env bash
# Downloads the newest live ISO of one Linux distro, boots it in a QEMU
# virtual machine, and saves a screenshot every 30 seconds.
# Usage: boot-linux.sh <distro> <out-dir> [minutes]
# Needs: qemu-system-x86, ovmf, python3-pil (and /dev/kvm for speed).
set -euo pipefail

DISTRO="$1"
OUT_DIR="$2"
MINUTES="${3:-8}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${WORK_DIR:-$PWD/work}"
mkdir -p "$OUT_DIR" "$WORK"

URL="$("$HERE/linux-iso-url.sh" "$DISTRO")"
ISO="$WORK/$(basename "$URL")"
echo "Newest $DISTRO: $URL"
echo "$DISTRO: $(basename "$URL")" > "$OUT_DIR/version.txt"
[[ -f "$ISO" ]] || curl -fL --retry 5 --retry-delay 10 -o "$ISO" "$URL"

# UEFI firmware with a writable copy of its settings.
cp /usr/share/OVMF/OVMF_VARS_4M.fd "$WORK/vars.fd"
MON="$WORK/monitor.sock"
rm -f "$MON"

qemu-system-x86_64 \
  -machine q35,accel=kvm:tcg -cpu max -smp 4 -m 6144 \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd \
  -drive if=pflash,format=raw,file="$WORK/vars.fd" \
  -cdrom "$ISO" -boot d \
  -device virtio-vga -display none \
  -netdev user,id=n0 -device virtio-net-pci,netdev=n0 \
  -monitor unix:"$MON",server,nowait \
  -daemonize -pidfile "$WORK/qemu.pid"

mon() { python3 "$HERE/qemu-monitor.py" "$MON" "$@"; }
for _ in $(seq 1 30); do [[ -S "$MON" ]] && break; sleep 1; done

# Pick the "start live system" entry in the boot menu. Fedora's default
# entry checks the disc first (slow), so move up to "Start Fedora".
sleep 12
case "$DISTRO" in
  fedora) mon "sendkey up" "sendkey ret" ;;
  *)      mon "sendkey ret" ;;
esac

shots=$(( MINUTES * 2 ))
for i in $(seq 1 "$shots"); do
  sleep 30
  n=$(printf '%02d' "$i")
  mon "screendump $WORK/$DISTRO-$n.ppm"
done
sleep 1

# QEMU saves PPM images; turn them into PNG and keep the last as the main photo.
python3 - "$WORK" "$OUT_DIR" "$DISTRO" <<'PY'
import glob, os, shutil, sys
from PIL import Image
work, out, distro = sys.argv[1:]
pngs = []
for ppm in sorted(glob.glob(os.path.join(work, distro + "-*.ppm"))):
    png = os.path.join(out, os.path.basename(ppm)[:-4] + ".png")
    Image.open(ppm).save(png)
    pngs.append(png)
if pngs:
    shutil.copy(pngs[-1], os.path.join(out, distro + ".png"))
print("Converted", len(pngs), "screenshots")
PY

kill "$(cat "$WORK/qemu.pid")" 2>/dev/null || true
echo "Saved $shots screenshots to $OUT_DIR"
