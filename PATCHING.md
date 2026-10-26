# Update to 2.25.2

Copy the contents of `bld-letter-memo-web-2.25.2/` into your existing project,
replacing matching files. Place the contents
directly in the project folder. Patching and GitHub Pages deployment are
unchanged.

Run these commands separately from Terminal inside your project folder:

```bash
git add -A
git commit -m "Enter cube corners and edges together clockwise"
git push
```

If Git says "nothing to commit", still run `git push` to publish any local
commit already waiting. Wait for GitHub Actions, reload, and confirm **2.25.2**
in the header or browser-tab title. Command+Shift+R can refresh the build on
macOS. Keep browser storage; no import, reset or migration is needed.

## What changes

- The 2D cube auto-advances clockwise around each face's perimeter, starting
  at its top-left corner and mixing corners and edges as you type.
- Faces follow U / L / F / R / B / D order. Centers and all stickers on locked
  buffer pieces are skipped automatically, including after changing buffers.
- Clicking a sticker resumes that same path from the chosen position.
  Backspace moves backwards along it and clears the correct category.
- The entry hint explains the clockwise order. Face cards keep their existing
  category-specific order. Both editors continue to use the same saved data.

Existing letter assignments are preserved. Models, AppState, browser storage,
backup format, tracing, preferred/temporary cycle breaks, Progressive Memo,
Timer, Letter Pairs, ratings, aliases and histories are unchanged. First-scheme
creation and one-flip-at-a-time recall from 2.25.1 are retained.
Data version remains 15; dependencies and deployment workflow are unchanged.

## Validation

100 automated tests pass. Updated regression cases type through all six faces
with default and changed buffers, starting from either Face cards category.
They check the clockwise mixed sequence, category-specific saves, backwards
entry, unchanged cube geometry and Face cards order. Existing tracing,
persistence, theme, layout and practice tests also pass. Browser rendering
remains unverified here; no live deployment was performed.
