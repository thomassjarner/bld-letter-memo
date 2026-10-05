# Update to 2.24.2

Copy the contents of `bld-letter-memo-web-2.24.2/` into your existing project,
replacing matching files and including the new files. Place the contents directly
in the project folder. The GitHub Pages deployment process is unchanged.

Run these commands from Terminal inside your existing project folder:

```bash
git add -A
git commit -m "Remove center letters and fit cube to screen"
git push
```

Run the commands separately. If Git says "nothing to commit", still run
`git push` to publish any commit already waiting locally.

Wait for GitHub Actions, then reload and confirm **2.24.2** in the header or
browser-tab title. Command+Shift+R can refresh the build on macOS. Keep browser
storage; no manual data migration or import is needed.

## Cube appearance

In **Letter Schemes → Edges/Corners → Editor → 2D cube**, center pieces now
show only their color. The net sizes itself using available height as well as
width. A shorter heading and compact controls leave more room for the cube.
Letter size adjusts with the stickers, and editing retains its square shape.

The physical net, memo orientation colors, locked buffers, duplicate warnings,
and Face cards option remain. Both editors still
share the same saved letters, capitalization, autosave, auto-advance and
Backspace behavior. Very small screens retain readable minimum-size stickers
and horizontal/vertical scrolling. Hover over a center to see its face name.

## Preservation and validation

Only the cube presentation, scheme-page layout, tests, release labels and documentation change.
All core logic, data models, state and persistence, Timer, Progressive Memo,
Letter Pairs, history, backups, dependencies and deployment workflow are unchanged.

79 automated tests pass, including height-only resizing, full-net bounds,
small-window scrolling, plain centers, focus, contrast, buffers and editor interchange.
Browser rendering remains unverified here. No live deployment was performed.
