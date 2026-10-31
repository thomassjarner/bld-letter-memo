# Update to 2.37.0

Copy all contents of `bld-letter-memo-web-2.37.0/` directly into your existing
`~/Desktop/letterpairscheme-helper-web/` project, replacing matching files and
including every new file. Include `core/corner_walkthrough.py` and
`ui/components/corner_walkthrough.py`. Do not put the release folder itself
inside the project. Patching and GitHub Pages deployment are unchanged.

Run in Terminal:

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Add scramble corner walkthrough and timer shortcuts"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, reload, and confirm **2.37.0** in the header or tab title.
Command+Shift+R can refresh the build on macOS. No package installation,
manual migration, import or storage reset is required.

## What changed

- **Method Library → Corner walkthrough** generates and animates the verified
  corner algorithms for a real scramble using the selected scheme, memo frame,
  corner buffer and saved cycle-break priorities/stickers.
- Uses saved preferred algorithms when valid, with verified built-in fallback
  warnings, setup support for other buffers and visual twist corrections.
- Leaves an odd final target pending for a separate parity algorithm. Even
  plans finish with solved corners; edges retain their physical scramble state.
- Three edge views: hidden colors/letters, initially solved, or actual scramble.
  Existing Show letters / Highlight pieces switches and simultaneous playback
  remain available. View modes do not modify the plan or user data.
- Cube-icon shortcuts from the Timer's current scramble and each saved solve.
  Existing timer layout, sessions/history, keyboard listener and result actions
  remain intact. Walkthrough routing is blocked during an active solve.

Data version stays 18. No settings reset or manual import is required.
Existing BLD tracing, temporary overrides, scheme/pair data, ratings, aliases,
case libraries, Timer and Progressive Memo behavior are preserved.

## Validation

**443 automated tests pass**, including all prior checks. New coverage
executes the gold scrambles with all 24 corner-buffer stickers and both twist
memo modes, all memo-frame/own-orientation combinations, saved and temporary
cycle-break stickers, preferred/fallback algorithms, visual twists, exact
unmatched-target parity residues, restored edges/centers, edge masking and
solved-edge visualization. UI checks cover bounded layouts, stale-plan handling,
light/dark colors, Timer/current/history shortcuts and unchanged saved data.

The Flet web Python runtime also verified Timer-to-walkthrough routing, complete
corner playback, parity reservation, edge modes and immutable saved data at six
screen sizes. Prior camera dragging, simultaneous playback, case comparison,
conversion, persistence/backups and themes also passed. Live browser client
rendering remains unverified; no live deployment was performed.

