# Simulator

Runs **iPhone, iPad, Apple Watch, Android (phone and tablet) and Windows** on
free machines borrowed from GitHub Actions, and takes a screenshot of each.

| Device | Runs on | Tool |
| --- | --- | --- |
| iPhone, iPad, Apple Watch | GitHub's macOS machine | Xcode simulators |
| Android phone (Pixel 7) and tablet (Pixel Tablet) | GitHub's Linux machine | Android emulator |
| Windows | GitHub's Windows machine | The real Windows desktop |

## How to use it

1. Open the **Actions** tab of this repository.
2. Click **Simulators** on the left, then **Run workflow**.
3. Wait about 5–10 minutes until the run shows a green check mark.
4. Open the run and download the screenshots at the bottom:
   `apple-screenshots`, `android-phone-screenshots`,
   `android-tablet-screenshots` and `windows-screenshots`.

It also runs automatically on every push to `main` and on every pull request.

## What's inside

- `.github/workflows/simulators.yml`: tells GitHub which machines to start and what to run.
- `scripts/screenshot-simulators.sh`: boots the newest iPhone, iPad and
  Apple Watch simulators, screenshots them, and lists every installed runtime.
- `scripts/screenshot-windows.ps1`: screenshots the Windows desktop.

You can also run the scripts on your own computer:

```
./scripts/screenshot-simulators.sh          # on a Mac with Xcode
pwsh ./scripts/screenshot-windows.ps1       # on Windows (add -MinimizeWindows to hide open windows)
```

## Notes

- There is no "Mac simulator": Mac apps run directly on the Mac.
- iPad simulators come with the iOS runtime.
- Windows is a real Windows machine, not a simulator.
- If an Apple runtime (e.g. watchOS) isn't installed, that device is skipped with a warning.
