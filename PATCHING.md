# Update to 2.42.0

Copy all contents of `bld-letter-memo-web-2.42.0/` into your existing
`~/Desktop/letterpairscheme-helper-web/` project, replacing matching files.
Include the new `core/corner_trainer.py`, `ui/components/corner_trainer.py` and
`tests/test_corner_trainer.py` files. Do not put the release folder
itself inside the project. The update process is unchanged.

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Add 3-style corner recall trainer"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, refresh and confirm **2.42.0** in the header/tab title.
Command+Shift+R can refresh the build on macOS.

Open **Method Library → Corner trainer**. Choose filters and Start session.
Apply each setup to a solved cube, recall the alg, then rate Remembered/Missed.

No dependency, storage-key or data-format changes are required. Data version
remains 18. Trainer results live in the current page session; existing saved
learning labels and histories are unchanged.
The existing BLD logic, data, algorithms, temporary cycle breaks,
timer/practice histories, persistence and import/export are preserved.

See `UI_CHANGES.md` for the UI review and `CHANGELOG.md` for release history.
