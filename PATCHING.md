# Update to 2.22.2

Copy the contents of `bld-letter-memo-web-2.22.2/` into your existing project
folder, replacing matching files. Do not nest the versioned folder inside the
project. The normal GitHub Pages deployment process is unchanged.

After copying the files, run these commands from your existing Terminal window,
already inside the project:

```sh
git add -A &&
git commit -m "Clarify rating averages and compact letter pair rows" &&
git push
```

Wait for GitHub Actions, then reload and confirm **2.22.2** in the header or
browser-tab title. Command+Shift+R can refresh the build on macOS. Keep browser
storage; no data migration or import is needed.

## Changes

The two averages now explicitly identify ratings. Search checkboxes use native
compact proportions with smaller label text instead of rectangular width/height
constraints. Dictionary rows have slightly smaller type, less vertical padding,
and 32px word/rating editors. The existing scrolling viewport and responsive
columns remain in place.

Only Letter Pairs presentation, version labels, the existing layout test and
documentation change. The Timer file, core logic, models, repositories, state,
color handling, dependencies and deployment workflow are unchanged from 2.22.1.
Average calculations, search/filter behavior, aliases and rating callbacks are
unchanged.

## Validation

39 tests pass, including the original BLD, theme and Timer checks. Existing
Letter Pairs checks cover all 650 filtered pairs remaining reachable, viewport
resizing, typing, word commits, alias/rating edits, empty results and Stats.
The layout test now checks that search checkboxes have no forced dimensions.

Browser rendering remains unverified in this environment. No live deployment
was performed here.
