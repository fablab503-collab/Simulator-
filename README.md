# Simulator

Runs **iPhone, iPad, Apple Watch, Android (phone and tablet), Windows and
8 Linux versions** on free machines borrowed from GitHub Actions, and takes a
screenshot of each. Everything uses the newest version available.

| Device | Runs on | Tool |
| --- | --- | --- |
| iPhone, iPad, Apple Watch | GitHub's macOS machine | Xcode simulators |
| Android phone (Pixel 7) and tablet (Pixel Tablet) | GitHub's Linux machine | Android emulator |
| Mac: Tahoe, Sequoia, Sonoma (Apple M chip) and Sequoia (Intel chip) | GitHub's macOS machines | The real Mac desktop |
| Windows | GitHub's Windows machine | The real Windows desktop |
| Ubuntu, Fedora, Debian, Mint, Arch, openSUSE, Pop!_OS, Omarchy | GitHub's Linux machine | The newest live ISO, booted in a QEMU virtual machine |

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
- Older macOS versions (Ventura and earlier) can't run on GitHub. Apple only allows macOS on
  Apple hardware, and GitHub no longer offers those versions.
- iPad simulators come with the iOS runtime.
- Windows is a real Windows machine, not a simulator.
- Linux screenshots show the live (try-before-install) desktop. Arch has no desktop
  by default, so it shows a text console. Omarchy's ISO is an installer, so it shows
  the installer's first screen.
- If an Apple runtime (e.g. watchOS) isn't installed, that device is skipped with a warning.
