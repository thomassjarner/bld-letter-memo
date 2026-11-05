# Update to 2.41.0

Copy all contents of `bld-letter-memo-web-2.41.0/` into your existing
`~/Desktop/letterpairscheme-helper-web/` project, replacing matching files.
Include the new `data/color_themes.py` and `tests/test_light_themes.py` files. Do not put the release folder
itself inside the project. The update process is unchanged.

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Add five light color themes"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, refresh and confirm **2.41.0** in the header/tab title.
Command+Shift+R can refresh the build on macOS.

Choose a theme under **Settings → Appearance → Light color theme**. Turn off
Dark mode to apply it to the site. The preview is available in either mode.

No dependency or storage-key changes are required. Data version remains 18,
with one optional saved preference; older backups default to Classic Teal.
The existing BLD logic, data, algorithms, temporary cycle breaks,
timer/practice histories, persistence and import/export are preserved.

See `UI_CHANGES.md` for the UI review and `CHANGELOG.md` for release history.
