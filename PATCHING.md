# Update to 2.22.0

Copy the contents of `bld-letter-memo-web-2.22.0/` into your existing project
folder, replacing matching files. Do not copy the versioned wrapper as a new
nested folder. Use the same GitHub Pages deployment workflow.

After the files are copied, run these commands from your existing Terminal
window, already inside the project:

```sh
git add -A &&
git commit -m "Make timer spacious and improve solve history" &&
git push
```

After GitHub Actions finishes, reload the site and check for **2.22.0** in
the header or browser tab title. Command+Shift+R can refresh the browser build
on macOS. Keep browser storage; no data import or migration is required.

## What changed

The timer's scramble and Previous/Next controls share one row. Wide screens
place the larger timer to the left of solve history; narrow screens stack them.
History uses a bounded ListView and a visible scrollbar. Scroll the first 50
solves and click Older solves to reach older records, 50 at a time. In compact
layouts, use the Session statistics icon in the history header to see all averages.
The brand mark is a static outline cube without a filled button-like background.

## Verification

32 automated tests pass. Existing BLD logic, data repositories, models, state,
theme-color handling, dependencies, entrypoint and deployment workflow were
verified byte-identical to 2.21.2. Keyboard and timing methods were also compared
and are unchanged. Resize tests retain the live timer and keyboard-listener
instances. History tests reach all records and exercise actions on the oldest
solve without changing other saved data.

Browser visual testing was not available in this environment. After deployment,
check a wide and a narrow window, both themes, long-history scrolling, and
Space-key timing after a resize. No live deployment was made during development.
