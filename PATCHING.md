# Update to 2.26.0

Copy the contents of `bld-letter-memo-web-2.26.0/` into your existing project,
replacing matching files and including new files and the `core/vendor/` folder.
Place the contents
directly in the project folder. Patching and GitHub Pages deployment are
unchanged.

Run these commands separately from Terminal inside your project folder:

```bash
git add -A
git commit -m "Add edges-only and corners-only timer sessions"
git push
```

If Git says "nothing to commit", still run `git push` to publish any local
commit already waiting. Wait for GitHub Actions, reload, and confirm **2.26.0**
in the header or browser-tab title. Command+Shift+R can refresh the build on
macOS. Keep browser storage; no import, reset or migration is needed.

## What changes

- Timer Session 2 is displayed as **edges only**. Its scrambles leave corners
  fully solved. Session 1 retains the normal full-cube generator.
- Session 3 is displayed as **corners only**. Without 3-style, edges remain
  fully solved and corner permutation is even.
- With 3-style enabled, each corner-only scramble has a 50% chance of odd
  corner parity. Those cases swap the configured edge buffer and helper edge;
  all other edges stay solved. The existing memo parity swap cancels that pair.
- Focused scrambles honor memo orientation and own-orientation settings.
  Relevant setting changes refresh the focused scramble stack. Next/previous,
  stopping, automatic advance, penalties and history follow the selected mode.
- Existing session IDs, saved times, penalties and scrambles are preserved
  under the new display names, including older full-cube times in those slots.
- The solver source and MIT notice are bundled. No external service, new
  Python package installation or deployment change is required. Native Python
  uses Node if available; otherwise its legal construction fallback is longer.

Models, BLD simulation/tracing, browser storage keys, backup format, Progressive
Memo, Letter Pairs, ratings and aliases are preserved. The Timer layout,
clockwise mixed cube entry and temporary cycle-break sticker picker are retained.
Data version remains 15; dependencies and deployment workflow are unchanged.

## Validation

145 automated tests pass, including the unchanged gold scramble checks and
Timer layout tests. Additional checks generated 192 focused scrambles in the
Flet web Python runtime across all 24 memo orientations; every output was at
most 21 moves and preserved the category/parity constraints. Tests also cover
all 132 buffer/helper pairs, sample legality, fair parity draws, native fallback,
session history, penalties, backup round trips, persisted active sessions,
invalid settings and protection against stale history actions after import.
Browser rendering remains unverified here; no live deployment was performed.
