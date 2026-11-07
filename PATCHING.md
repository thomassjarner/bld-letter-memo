# Update to 2.43.0

Copy all contents of `bld-letter-memo-web-2.43.0/` into your existing
`~/Desktop/letterpairscheme-helper-web/` project, replacing matching files.
Include the new `tests/test_progressive_memo_corrections.py` file. Do not put the release folder
itself inside the project. The update process is unchanged.

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Fix Progressive Memo recall navigation and single letters"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, refresh and confirm **2.43.0** in the header/tab title.
Command+Shift+R can refresh the build on macOS.

Open **Practice → Progressive Memo**. During recall, use Previous/Left Arrow
to correct an answer and Skip/Right Arrow to leave that answer blank.

No dependency, storage-key or data-format changes are required. Data version
remains 18. Existing histories and the 3-style tracer are unchanged; corrected
answers are saved normally when the current Progressive Memo attempt finishes.
The existing BLD logic, data, algorithms, temporary cycle breaks,
timer/practice histories, persistence and import/export are preserved.

See `UI_CHANGES.md` for the UI review and `CHANGELOG.md` for release history.
