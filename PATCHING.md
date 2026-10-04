# Updating 2.20.2 → 2.21.0

The patch and deployment process has not changed. This is still the same
Flet 0.86.3 / Python app, published by the existing GitHub Pages workflow.
No React migration, new backend, dependency change, or data migration is required.

## Apply the update

1. In the current app, use **Settings → Export backup** to keep a copy of your data.
2. Extract this ZIP. Copy the **contents** of `bld-letter-memo-web-2.21.0/`
   into your existing project root, overwriting matching files. `main.py`,
   `requirements.txt`, and `ui/` must remain at the project root; do not add
   the versioned wrapper folder as a new level in your repository.
3. Include the new files `ui/design.py` and `ui/pages/home_page.py`.
   If you previously patched only existing files, this is the one detail to watch.
4. Run your normal checks:

   ```sh
   python -m pip install -r requirements.txt -r requirements-dev.txt
   python -m pytest
   ```

5. Commit and push to the same repository's `main` branch. The existing
   GitHub Actions workflow publishes to the same GitHub Pages URL.
6. Reload the app. Home is now the starting destination. Use **Timer** in
   the main navigation or **Practice → Blind Timer** to time attempts.

You do not need to import a backup for this update. Keep the same site origin
and browser profile, and do not clear site storage. Browser storage does not
move automatically to a different domain, browser, or device; use export/import
if you deliberately move the app.

## Files changed

- `ui/app.py` — new shell, Home-first navigation, theme shortcut, narrow-screen navigation.
- `ui/design.py` — new shared theme tokens and presentation components.
- `ui/pages/home_page.py` — new introduction and four workflow routes.
- `ui/pages/letter_schemes_page.py` — workspace heading and scheme panel styling.
- `ui/components/sticker_grid.py` — face cards and letter-field styling.
- `ui/pages/letter_pairs_page.py` — heading, filter panel, scrollable content.
- `ui/pages/scramble_memo_page.py` — separate input/output panels.
- `ui/pages/practice_page.py` — activity hub and compact timer presentation.
- `ui/pages/settings_page.py` — appearance, ratings, and backup panels.
- `tests/test_navigation.py` — navigation and theme regression checks.
- `README.md`, `PATCHING.md` — release and update documentation.

All `core/`, `data/`, `ui/state.py`, original test files, dependencies,
`main.py`, and `.github/workflows/deploy.yml` are byte-identical to 2.20.2.
Storage keys and backup formats are unchanged. The separate Timer and Practice
controls and asynchronous keyboard-focus behavior from 2.20.2 are retained.

## Validation

- 19 automated checks pass: 13 original checks plus 6 new presentation-wiring checks.
- The new checks cover Home routes, navigation order, both Timer entry points,
  return navigation, sending a scramble to Memo, navigation preferences, and theme persistence.
- These are Python control-tree tests. They do not simulate Flutter rendering,
  actual browser keyboard focus, or a browser storage round trip.
- Browser visual/keyboard QA could not be completed in the development environment
  because the Chromium download failed. No deployment was performed.

After deployment, check Home in both themes; open Timer from both entry points;
make a Space-key attempt; switch away and return; and confirm your existing schemes,
words, ratings, aliases, and sessions are present. Check long-history scrolling
and backup export/import using a separate test browser profile.

Progressive Memo, Delayed Recall, and Letter Pair Drill were placeholders in
2.20.2 and remain clearly marked **Coming soon**. This release does not implement
their training logic.
