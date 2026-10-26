# Update to 2.25.1

Copy the contents of `bld-letter-memo-web-2.25.1/` into your existing project,
replacing matching files and including the new test file. Place the contents
directly in the project folder. Patching and GitHub Pages deployment are
unchanged.

Run these commands separately from Terminal inside your project folder:

```bash
git add -A
git commit -m "Fix scheme creation, cube entry order and flip recall"
git push
```

If Git says "nothing to commit", still run `git push` to publish any local
commit already waiting. Wait for GitHub Actions, reload, and confirm **2.25.1**
in the header or browser-tab title. Command+Shift+R can refresh the build on
macOS. Keep browser storage; no import, reset or migration is needed.

## What changes

- A fresh browser opens a first-scheme form with a name field and Create button
  in the main Letter Schemes area. Enter also creates and opens the scheme.
  Sidebar creation likewise opens the newly created scheme immediately.
- The 2D cube uses the same clockwise category sequence as Face cards, skipping
  locked buffer stickers and centers. Both edges and corners remain editable.
- Progressive Memo groups letter-based flips on screen during memo, then
  recalls one flip pair per answer. JP / VO are two separate confirmations,
  instead of one JPVO answer. Results label the flips individually.

Older grouped flip history is displayed as stored. Corner twist recall, visual
flip preferences, actual tracing and preferred/temporary cycle breaks are
preserved. Models, AppState, browser storage keys/repositories, backup format,
Timer, Letter Pairs, ratings, aliases and other saved histories are unchanged.
Data version remains 15; dependencies and deployment workflow are unchanged.

## Validation

98 automated tests pass. New regression cases cover creation from clean data
in all navigation styles on wide/narrow screens, Enter submission, stale active
schemes, opening new schemes, clockwise entry in each category, real two-flip
scrambles, execution order, separate Space confirmations, scoring, persistence
and old grouped history. Browser rendering remains unverified here; no live
deployment was performed.
