# Update to 2.40.0

Copy all contents of `bld-letter-memo-web-2.40.0/` into your existing
`~/Desktop/letterpairscheme-helper-web/` project, replacing matching files.
Include the new `UI_CHANGES.md` and test file. Do not put the release folder
itself inside the project. The update process is unchanged.

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Improve navigation and consistency across the training workspace"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, refresh and confirm **2.40.0** in the header/tab title.
Command+Shift+R can refresh the build on macOS.

This is a UI update. No dependency, storage-key or data-format changes are
required. The existing BLD logic, data, algorithms, temporary cycle breaks,
timer/practice histories, persistence and import/export are preserved.

See `UI_CHANGES.md` for the UI review and `CHANGELOG.md` for release history.
