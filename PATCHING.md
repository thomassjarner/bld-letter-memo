# Update to 2.25.3

Copy the contents of `bld-letter-memo-web-2.25.3/` into your existing project,
replacing matching files and including the new test file. Place the contents
directly in the project folder. Patching and GitHub Pages deployment are
unchanged.

Run these commands separately from Terminal inside your project folder:

```bash
git add -A
git commit -m "Allow any sticker in temporary cycle breaks"
git push
```

If Git says "nothing to commit", still run `git push` to publish any local
commit already waiting. Wait for GitHub Actions, reload, and confirm **2.25.3**
in the header or browser-tab title. Command+Shift+R can refresh the build on
macOS. Keep browser storage; no import, reset or migration is needed.

## What changes

- Click an underlined cycle-break target in Scramble Memo to open the picker.
  Every available edge offers both stickers; every corner offers all three.
- Buttons show your scheme letter and the sticker ID. The saved preferred
  sticker is marked, and the exact selected sticker is highlighted.
- Selecting a sticker retraces the memo from that exact target. Alternative
  stickers on the highest-priority piece work too. Pieces stay in saved
  priority order; the saved scheme and its preferences are never modified.
- Reset to priority restores the recommended piece and preferred sticker.
  Changing the scramble or scheme clears temporary choices as before.

Existing piece-only overrides still use saved preferred stickers. Explicit
sticker choices are validated against the available pieces at that break.
Simulation, default tracing, models, AppState, browser storage, backup format,
Progressive Memo, Timer, Letter Pairs, ratings, aliases and histories are
preserved. Clockwise mixed cube entry from 2.25.2 is retained.
Data version remains 15; dependencies and deployment workflow are unchanged.

## Validation

113 automated tests pass, including the unchanged gold scramble checks.
New cases exercise every available sticker for edges/corners, non-canonical
saved preferences, rotated frames, own orientation, parity mode, invalid and
unavailable targets, picker clicks in both themes, exact selection highlights,
resets, and unchanged saved data. Existing UI and practice tests also pass.
Browser rendering remains unverified here; no live deployment was performed.
