# Simulator

Runs **iPhone, iPad, Apple Watch, Android (phone, tablet and folding phone), Windows and
8 Linux versions** on free machines borrowed from GitHub Actions, and takes a
screenshot of each. Everything uses the newest version available.

| Device | Runs on | Tool |
| --- | --- | --- |
| iPhone, iPad, Apple Watch (versions 27, 26, 18 and 17) | GitHub's macOS machines | Xcode simulators |
| Android phone, tablet and folding phone (newest), plus every Android from 5 to 15 | GitHub's Linux machine | Android emulator |
| Mac: macOS 27, Tahoe, Sequoia (Apple M chip) and Sequoia (Intel chip) | GitHub's macOS machines | The real Mac desktop |
| Windows 11 (ARM), Server 2025, Server 2022 | GitHub's Windows machines | The real Windows desktop |
| Ubuntu, Fedora, Debian, Mint, Arch, openSUSE, Pop!_OS, Omarchy | GitHub's Linux machine | The newest live ISO, booted in a QEMU virtual machine |
| Older Ubuntu: 24.04, 22.04, 20.04, 18.04, 16.04, 14.04, 12.04, 10.04, 8.04, 6.06 and 4.10 (the first, 2004) | GitHub's Linux machine | The archived live ISO, in QEMU |
| ReactOS (free Windows XP look-alike), FreeDOS, Haiku, FreeBSD, ChromeOS Flex | GitHub's Linux machine | Their official free download, in QEMU |
| Game consoles: NES, SNES, Game Boy, GBA, Sega Genesis, PS1, PSP, GameCube | GitHub's Linux machine | RetroArch running a free homebrew game from libretro |
| PS2 (PCSX2), PS3 (RPCS3 + Sony's free system software), PS4 (shadPS4) | GitHub's Linux machine | The emulator's own screen |

## Gimmich: everything in one download

After each run, the **Gimmich** step puts every system's photos, one picture of all of
them together (`gimmich-all.png`), and a list of every version (`versions.md`) into a
single download:

- **Newest weekly bundle:** https://github.com/fablab503-collab/Simulator-/releases/download/gimmich-latest/gimmich.zip
- **Any single run:** open the run on the Actions tab and download `gimmich`.

## How to use it

1. Open the **Actions** tab of this repository.
2. Click **Simulators** on the left, then **Run workflow**.
3. Wait about 5–10 minutes until the run shows a green check mark.
4. Open the run and download the screenshots at the bottom.
   The run's summary page lists every version that was used.

## Staying up to date

- It runs **every Monday** by itself, and on every push to `main` and every pull request.
- Apple and Windows use GitHub's newest machines; the script picks the newest simulators on them.
- Android asks Google's SDK for the newest version each run.
- Linux looks up the newest ISO on each project's official site each run (`scripts/linux-iso-url.sh`).
- **Dependabot** opens a pull request when the GitHub Actions helpers have a new version.

## What's inside

- `.github/workflows/simulators.yml`: tells GitHub which machines to start and what to run.
- `scripts/screenshot-simulators.sh`: boots the newest iPhone, iPad and
  Apple Watch simulators, screenshots them, and lists every installed runtime.
- `scripts/screenshot-windows.ps1`: screenshots the Windows desktop.
- `scripts/screenshot-mac.sh`: screenshots a Mac desktop and records its macOS version and chip.
- `scripts/linux-iso-url.sh`: finds the newest download for each Linux.
- `scripts/boot-linux.sh`: boots that Linux in a virtual machine and screenshots it every 30 seconds.

You can also run the scripts on your own computer:

```
./scripts/screenshot-simulators.sh          # on a Mac with Xcode
pwsh ./scripts/screenshot-windows.ps1       # on Windows (add -MinimizeWindows to hide open windows)
```

## Notes

- There is no "Mac simulator": Mac apps run directly on the Mac, so the Mac rows are real Macs.
- Older macOS versions (Sonoma and earlier) can't run on GitHub. Apple only allows macOS on
  Apple hardware, and GitHub no longer offers those versions.
- iPad simulators come with the iOS runtime.
- Game consoles use only free homebrew games and Sony's free PS3 system software. No
  commercial games or console BIOS files are downloaded. There is no real PS5 emulator.
- Windows is a real Windows machine, not a simulator. Older Windows (XP, Vista, 7, 8)
  isn't included: Microsoft no longer offers it for download and it gets no security fixes.
- Linux screenshots show the live (try-before-install) desktop. Arch has no desktop
  by default, so it shows a text console. Omarchy's ISO is an installer, so it shows
  the installer's first screen.
- If an Apple runtime (e.g. watchOS) isn't installed, that device is skipped with a warning.
