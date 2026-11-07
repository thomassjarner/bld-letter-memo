# Update to 2.44.0

Copy all contents of `bld-letter-memo-web-2.44.0/` into your existing
`~/Desktop/letterpairscheme-helper-web/` project, replacing matching files.
Include the new `tests/test_progressive_memo_constraints.py` file. Do not put the release folder
itself inside the project. The update process is unchanged.

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Preserve recall answers and add Progressive Memo constraints"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, refresh and confirm **2.44.0** in the header/tab title.
Command+Shift+R can refresh the build on macOS.

Open **Practice → Progressive Memo** and choose the Constraints before Start.
During recall, Right Arrow/Next now preserves entered answers; Skip is only for
a prompt that has no retained letters. Previous/Left Arrow restores an answer.

No dependency or storage-key changes are required. Data version remains 18,
with optional constraint preferences/attempt metadata. Old backups import
normally with the prior defaults, and existing scores/times are unchanged.
The existing BLD logic, data, algorithms, temporary cycle breaks,
timer/practice histories, persistence and import/export are preserved.

See `UI_CHANGES.md` for the UI review and `CHANGELOG.md` for release history.
