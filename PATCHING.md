# Update to 2.46.0

Copy all contents of `bld-letter-memo-web-2.46.0/` into your existing
`~/Desktop/letterpairscheme-helper-web/` project, replacing matching files.
Do not put the release folder itself inside the project.

The copy/commit/push process is unchanged. Include the new `ui/feature_icons.py`
and `tests/test_home_workspaces.py` files, plus all updated files. Continue to
copy the hidden `.github/` folder and `scripts/`/`web_preview/` to retain the
branded link-preview deployment from 2.45.0. Finder can hide `.github`;
Command+Shift+. shows hidden files.

If you extracted the ZIP into Downloads, this terminal command copies all
contents, including `.github`, without deleting anything from your project:

```bash
rsync -av ~/Downloads/bld-letter-memo-web-2.46.0/ ~/Desktop/letterpairscheme-helper-web/
```

Adjust the source path if you extracted it elsewhere. Then use the usual push:

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Group Home by activity and add theme-aware feature icons"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, refresh and confirm **2.46.0** in the header/tab title.
Command+Shift+R can refresh the build on macOS.

Home should show **Set up your memo**, **Analyze a scramble**, **Learning
material**, and **Practice**. Try the new direct Scramble walkthrough,
Algorithm Playground and Progressive Memo links. The original Method Library,
Practice and Timer routes remain available. Switch themes to see the same
feature icons adapt to the chosen colors.

No dependency or storage-key changes are required. Data version remains 18,
with the existing optional constraint preferences/attempt metadata. Old
backups import normally, and existing scores/times are unchanged.
The existing BLD logic, data, algorithms, temporary cycle breaks,
timer/practice histories, persistence and import/export are preserved.

See `UI_CHANGES.md` for the UI review and `CHANGELOG.md` for release history.
