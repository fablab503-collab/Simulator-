# Simulator

Runs Apple's **iPhone, iPad and Apple Watch simulators** on a free Mac
borrowed from GitHub Actions, and takes a screenshot of each one.

## How to use it

1. Open the **Actions** tab of this repository.
2. Click **Simulators** on the left, then **Run workflow**.
3. Wait a few minutes until the run shows a green check mark.
4. Open the run and download **simulator-screenshots** at the bottom.

It also runs automatically every time something is pushed to `main`.

## What's inside

- `.github/workflows/simulators.yml`: tells GitHub to start a Mac and run the script.
- `scripts/screenshot-simulators.sh`: boots the newest iPhone, iPad and
  Apple Watch simulators, screenshots them, and lists every installed runtime.

You can also run the script on your own Mac (with Xcode installed):

```
./scripts/screenshot-simulators.sh
```

## Notes

- There is no "Mac simulator": Mac apps run directly on the Mac.
- iPad simulators come with the iOS runtime.
- If a runtime (e.g. watchOS) isn't installed, that device is skipped with a warning.
