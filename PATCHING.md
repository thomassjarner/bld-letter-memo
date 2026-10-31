# Update to 2.39.0

Copy all contents of `bld-letter-memo-web-2.39.0/` directly into your existing
`~/Desktop/letterpairscheme-helper-web/` project. Replace matching files and
include every new file, especially `core/commutator_playback.py`. Do not put the
release folder itself inside the project. The update process is unchanged.

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Add component playback and synchronized commutator tracking"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, reload and confirm **2.39.0** in the header or tab title.
Command+Shift+R can refresh the build on macOS.

## Changes

- Select **Components** beside the cube's speed selector to pause after each
  written commutator component. Use **Continue** for the next part.
- Commutator notation appears beneath the move list, with distinct A/B colours,
  a synchronized current-move highlight and setup/undo labels.
- Component mode follows the written notation; normal playback keeps its usual
  cleanup. Switching mode restarts the current algorithm. Both executions finish
  at the same cube state. A component can contain several moves.
- Applies to corner cases, Playground, Commutator Lesson and Scramble walkthrough.
  Existing pause-between-algorithms and simultaneous-move controls still work.
- Walkthrough jumps, edge modes and editor return retain the correct position.
  UF preview, untouched twists and the compact workspace remain in place.

No dependency, saved-source, data-format or storage-key changes. Existing letter
schemes, pairs, ratings, aliases, tracing, cycle breaks, case preferences, timer
and practice history, persistence and import/export retain their behavior.

## Validation

532 automated tests pass, including the original BLD gold tests. New coverage
checks written components, nested setups, undo/repetition, raw recovery, cleaned
move attribution, phase pauses, simultaneous boundaries, stale tasks, viewer
mode changes, edge-view offsets, editor return, themes and unchanged saved data.
The Flet web Python runtime also checks all Method Library viewers and the
walkthrough at six screen sizes. Actual browser-client rendering is not
measured here. No live deployment is performed by this release package.
