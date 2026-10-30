# Update to 2.30.0

Copy the contents of `bld-letter-memo-web-2.30.0/` into your existing project,
replacing matching files and including all new files/folders. Put the contents
directly in `~/Desktop/letterpairscheme-helper-web/`, rather than placing the
release folder inside it. Patching and deployment are unchanged.

Run in Terminal:

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Compact Method Library and simplify playback"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, reload, and confirm **2.30.0** in the header or tab title.
Command+Shift+R can refresh the build on macOS. No new package installation,
manual migration, import or storage reset is required.

## What changed

- **The cube comes first** when opening a case. Large screens place algorithm
  tools beside it with independent scrolling; smaller screens put editing
  below the cube. New case selection resets the view to the top and closes
  editing, notes and the mobile case browser.
- Header, filter fields, case rows, playback controls and spacing are more
  compact. More filters holds status/favorites; checkboxes have natural sizes.
  Empty messages no longer create blank space.
- Open **Edit / replace alg** to paste, preview, save/use, copy or delete an
  alternative. Preferred choices, notes and progress retain their behavior.
- Default playback and the move display combine matching turns and remove
  cancellations, including across commuting same-axis moves. Counters and
  stepping follow that clean execution. Saved source notation is unchanged.
  **View options & stages → Original commutator stages** keeps the original
  setup/A/B playback available for study.

Data version remains 16. The supplied collection, case identities, personal
algorithms/preferences/progress/notes/favorites, schemes, pairs/ratings/aliases,
tracing, temporary cycle-break overrides, focused scrambles, Timer history,
Progressive Memo, browser persistence and import/export retain their behavior.
No data is rewritten automatically. Dependencies and deployment are preserved.

## Validation

294 automated tests pass, including all previous checks. New checks cover
initial cube visibility at seven viewport sizes, independent editing panes,
collapsed state, scroll reset, themes/checkbox geometry, cancellation cleanup,
exact full cube effects for every supplied/setup alternative, mixed notation,
and original commutator stages. The Flet web Python runtime also verified
layout/control behavior, clean effects, saves/backups and timed playback.
Actual browser client rendering remains unverified here; no live deployment
was performed.
