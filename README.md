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

## Try the Gimmich app on every device

The **Gimmich on devices** workflow (`.github/workflows/gimmich.yml`) takes the Gimmich app from
[fablab503-collab/airbridge](https://github.com/fablab503-collab/airbridge) and tries it on:

| Device | What happens |
|---|---|
| iPhone, iPad (newest simulators, real Safari) | opens the Studio, *Connect a device* and Camera pages |
| Apple Watch | home screen only: watchOS has no web browser, so there is nothing of Gimmich to open |
| Android phone (Pixel 7) and tablet (Pixel Tablet) emulators | installs the Gimmich Camera app, connects it with the `gimmich://` link, takes a photo with the emulator's pretend camera and checks the photo reached the server; then opens the Studio pages in the browser |

A small demo server (`scripts/gimmich-demo-server.py`) stands in for a real Gimmich/Immich: the real
Gimmich pages, with a pretend photo library. On Android it gets a temporary `https://` address
(Cloudflare quick tunnel), because the app only accepts secure addresses.

Run it from **Actions → Gimmich on devices → Run workflow** (you can pick which airbridge branch to test),
then download the `gimmich-…` screenshot folders at the bottom of the run.
Simulators have no real camera: on iPhone/iPad the Camera page shows its "no camera" message.
