# Update to 2.36.1

Copy all contents of `bld-letter-memo-web-2.36.1/` directly into your existing
`~/Desktop/letterpairscheme-helper-web/` project, replacing matching files and
including all new files. Do not put the release folder itself inside the
project. Patching and GitHub Pages deployment are unchanged.

Run in Terminal:

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Improve cube dragging responsiveness"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, reload, and confirm **2.36.1** in the header or tab title.
Command+Shift+R can refresh the build on macOS. No package installation,
manual migration, import or storage reset is required.

## What changed

- Camera dragging coalesces pending pointer updates and repaints just the canvas,
  with a shared maximum of 60 scheduled frames per second.
- Absolute pointer positions preserve movement across throttled events; release
  includes the final position. Pending frames are cancelled on case/camera/view
  changes, seeking and detaching the viewer.
- Camera updates during playback reuse the existing animation frames. Continuing
  a drag after playback finishes remains supported.
- Camera and turn trigonometry is reused within each projection frame, keeping
  the same geometry, colors, labels and highlights with less CPU work.

Data version stays 18. All settings, algorithms, BLD/training behavior, storage
keys, histories and import/export retain their behavior. The full ZIP update
workflow is unchanged. PC Chrome latency remains unmeasured here.

## Validation

**375 automated tests pass.** Drag regressions cover burst coalescing,
frame-rate scheduling across separate tasks, final pointer positions,
canvas-only updates, cancellation, replacement gestures, playback and 2D/
unmounted behavior. A separate comparison confirmed exact drawing output
against 2.36.0 for 160 camera/view/turn samples. The Flet web Python runtime
also checked burst/live dragging, final positions, stale-frame cancellation,
prior simultaneous playback, case browsing/comparison, conversion, saving,
backups and themes at six screen sizes. PC Chrome rendering latency was not
measured; no live deployment was performed.

