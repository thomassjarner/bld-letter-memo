# Update to 2.28.0

Copy the contents of `bld-letter-memo-web-2.28.0/` into your existing project,
replacing matching files and including all new files/folders. Put the contents
directly in `~/Desktop/letterpairscheme-helper-web/`, rather than placing the
release folder inside it. Patching and GitHub Pages deployment are unchanged.

Run these commands in Terminal:

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Improve Method Library navigation and smooth cube playback"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, reload, and confirm **2.28.0** in the header or tab title.
Command+Shift+R can refresh the build on macOS. No new package installation,
manual data migration, import or storage reset is required.

## What changed

- Open **Method Library** directly from Home or the main navigation tabs.
  It is now separate from Practice, with the same saved case collection.
- The overview offers **Commutator Lesson**, **Case Library** and **Algorithm
  Explorer** routes, direct U/U, U/D, D/U and D/D subset shortcuts, and a summary
  of your progress, favorites and saved algorithms. The selected section is
  highlighted, and Overview stays available from every section.
- 3D turns target **60 animation frames per second**, with eased motion and
  more frequent camera updates. Fast / Normal / Slow support up to 18 / 36 /
  72 frames per move. A timed schedule skips overdue frames on slower devices;
  actual frame rate depends on the browser and hardware. Only the canvas is
  republished during a turn, and the surrounding controls update at boundaries.
- Main navigation and the library adapt to narrow screens with scrolling and
  a stacked label-scheme picker. Timer remains a main tab and a Practice route.

Data version remains 16. Existing schemes, letter pairs/ratings/aliases,
tracing, cycle-break overrides, timer sessions/history, Progressive Memo
history, case alternatives/preferences/progress/notes/favorites, browser
persistence and backups retain their behavior. Import still replaces current
data as described in Settings. Dependencies and deployment are unchanged.

## Validation

250 automated tests pass, retaining all previous checks and adding Method
Library routes, overview/subset navigation, scroll bounds, frame scheduling,
slow rendering, seeking/cancellation, canvas-only updates and playback restart.
The Flet web Python runtime checked routes and all sections at three viewport
sizes, preserved data, and increased interpolated turn frames. Actual browser
client rendering remains unverified here; no live deployment was performed.
