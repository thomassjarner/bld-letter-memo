# Update to 2.47.0

Copy all contents of `bld-letter-memo-web-2.47.0/` into your existing
`~/Desktop/letterpairscheme-helper-web/` project, replacing matching files.
Do not put the release folder itself inside the project.

The copy/commit/push process is unchanged. Include the new
`core/blddb_corner_catalog.json`, `core/legacy_corner_algorithms.py`,
`tools/import_blddb_corners.py`, `third_party/blddb/` and tests, plus all updated
files. The JSON catalog is required in the deployed app. Continue to
copy the hidden `.github/` folder and `scripts/`/`web_preview/` to retain the
branded link-preview deployment from 2.45.0. Finder can hide `.github`;
Command+Shift+. shows hidden files.

If you extracted the ZIP into Downloads, this terminal command copies all
contents, including `.github`, without deleting anything from your project:

```bash
rsync -av ~/Downloads/bld-letter-memo-web-2.47.0/ ~/Desktop/letterpairscheme-helper-web/
```

Adjust the source path if you extracted it elsewhere. Then use the usual push:

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Replace corner alternatives with popularity-ranked BLDDB algorithms"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, refresh and confirm **2.47.0** in the header/tab title.
Command+Shift+R can refresh the build on macOS.

Open **Method Library → 3-style corner cases**. Choices should say **BLDDB**,
with a popularity rank and source-sheet count. The UFR–UBL–UBR case starts
with two groups of 23 sources; the second group has four spellings. The old
supplied/setup/generated alternatives should not be offered.

Personal algorithms, notes, statuses, favorites and explicit personal choices
are kept. Earlier builtin IDs stay in backup data but use the new most-popular
default until another choice is selected. No runtime connection to BLDDB is
required; the source attribution and pinned snapshot are bundled in this release.

No dependency or storage-key changes are required. Data version remains 18,
with the existing optional constraint preferences/attempt metadata. Old
backups import normally, and existing scores/times are unchanged.
The existing BLD logic, data, algorithms, temporary cycle breaks,
timer/practice histories, persistence and import/export are preserved.

See `UI_CHANGES.md` for the UI review and `CHANGELOG.md` for release history.
