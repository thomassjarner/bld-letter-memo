# Update to 2.24.1

Copy the contents of `bld-letter-memo-web-2.24.1/` into your existing project,
replacing matching files and including the new files. Place the contents directly
in the project folder. The GitHub Pages deployment process is unchanged.

Run these commands from Terminal inside your existing project folder:

```bash
git add -A
git commit -m "Polish 2D cube letter scheme editor"
git push
```

Run the commands separately. If Git says "nothing to commit", still run
`git push` to publish any commit already waiting locally.

Wait for GitHub Actions, then reload and confirm **2.24.1** in the header or
browser-tab title. Command+Shift+R can refresh the build on macOS. Keep browser
storage; no manual data migration or import is needed.

## Cube appearance

In **Letter Schemes → Edges/Corners → Editor → 2D cube**, every sticker now
uses its face color and a stable square shape. The form-style floating labels
and the six face captions are removed. Hover over a sticker to see its ID.
The letter stays centered during editing; focus changes only its outline.

The U/L/F/R/B/D center guides, physical net, memo orientation colors, locked
buffers, duplicate warnings, and Face cards option remain. Both editors still
share the same saved letters, capitalization, autosave, auto-advance and
Backspace behavior. Small screens retain horizontal and vertical scrolling.

## Preservation and validation

Only the cube presentation, its tests, release labels and documentation change.
All core logic, data models, state and persistence, Timer, Progressive Memo,
Letter Pairs, history, backups, dependencies and deployment workflow are unchanged.

78 automated tests pass, including editing focus/blur without changing square
geometry, all-sticker contrast in both themes, buffers and editor interchange.
Browser rendering remains unverified here. No live deployment was performed.
