# Update to 2.22.1

Copy the contents of `bld-letter-memo-web-2.22.1/` into your existing project
folder, replacing matching files. Do not nest the versioned folder inside the
project. The normal GitHub Pages deployment process is unchanged.

After copying the files, run these commands from your existing Terminal window,
already inside the project:

```sh
git add -A &&
git commit -m "Compact letter pair filters and fix scrolling" &&
git push
```

Wait for GitHub Actions, then reload and confirm **2.22.1** in the header or
browser-tab title. Command+Shift+R can refresh the build on macOS. Keep browser
storage; no data migration or import is needed.

## Changes

The Letter Pairs filter panel now uses the whole width in compact horizontal
rows. The heading is smaller. Dictionary and Stats each have an explicit
scrolling viewport and visible scrollbar. Two dictionary columns are retained
on wide screens; smaller windows use one column. On narrow screens, rating,
status and scheme information move below the pair/word line. Full scheme names
and detailed summaries are available in tooltips when shortened on screen.

Only Letter Pairs presentation, its viewport wiring, version labels, tests and
documentation change. The Timer file, core logic, models, repositories, state,
color handling, dependencies and deployment workflow are byte-identical to 2.22.0.
Pair search/filter logic, canonical pairs, aliases and rating callbacks were
compared with the previous release and are unchanged.

## Validation

39 tests pass, including the original BLD and Timer checks. New tests cover a
650-pair filtered result, all records remaining reachable, bounded layout at
multiple widths, preserving word fields during typing, commit behavior, aliases,
ratings, empty results and Stats resizing/scrolling.

Browser rendering was not available in this development environment. After
deployment, check Dictionary and Stats scrolling, filters and word editing in
both themes. No live deployment was performed here.
