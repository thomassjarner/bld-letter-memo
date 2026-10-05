# Update to 2.25.0

Copy the contents of `bld-letter-memo-web-2.25.0/` into your existing project,
replacing matching files and including the new `ui/components/sticker_tiles.py`.
Place the contents directly in the project folder. Patching and GitHub Pages
deployment are unchanged.

Run these commands separately from Terminal inside your project folder:

```bash
git add -A
git commit -m "Unify scheme editors and edit edges and corners together"
git push
```

If Git says "nothing to commit", still run `git push` to publish any local
commit already waiting. Wait for GitHub Actions, then reload and confirm
**2.25.0** in the header or browser-tab title. Command+Shift+R can refresh the
build on macOS. Keep browser storage; no import or migration is needed.

## Use the editors

Choose **Editor → Face cards** for the Edges/Corners tabs. The six compact
cards now use colored square inputs and reflow to fit the available width.
Sticker names remain visible above the cells.

Choose **Editor → 2D cube** for **All stickers**. Edit edges and corners on
one cube, with separate buffer selectors for each category. Centers have no
letters. Stars mark the exact tracing buffers; dots mark their other stickers.
Typing advances across the visible face positions; Backspace also works when
moving between edge and corner fields.

Both views share the compact controls, saved letters, autosave, capitalization,
fixed square geometry, light/dark contrast and a bounded scrolling workspace.
The last Face cards category is restored when returning to that editor.
Duplicate warnings are independent for edges and corners.

## Preservation and validation

The shared `ui/components/sticker_tiles.py` keeps tile appearance and buffer
locking consistent. Presentation callbacks route each sticker to its existing
category in AppState; core logic, data models, state, storage keys, repositories,
Timer, Progressive Memo, Letter Pairs, history, backups, dependencies and
deployment workflow remain unchanged. Data version remains 15.

83 automated tests pass, covering combined editing, Backspace across category
boundaries, both buffers, responsive cards, contrast, duplicates, switching
views and backup round trips. Browser rendering remains unverified here.
No live deployment was performed.
