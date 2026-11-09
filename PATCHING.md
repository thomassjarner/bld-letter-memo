# Update to 2.48.0

Copy all contents of `bld-letter-memo-web-2.48.0/` into your existing
`~/Desktop/letterpairscheme-helper-web/` project, replacing matching files.
Do not put the release folder itself inside the project.

The copy/commit/push process is unchanged. Replace all matching files and
retain the bundled `core/blddb_corner_catalog.json`, import tools, attribution
and tests. The JSON catalog is required in the deployed app. Continue to
copy the hidden `.github/` folder and `scripts/`/`web_preview/` to retain the
branded link-preview deployment from 2.45.0. Finder can hide `.github`;
Command+Shift+. shows hidden files.

If you extracted the ZIP into Downloads, this terminal command copies all
contents, including `.github`, without deleting anything from your project:

```bash
rsync -av ~/Downloads/bld-letter-memo-web-2.48.0/ ~/Desktop/letterpairscheme-helper-web/
```

Adjust the source path if you extracted it elsewhere. Then use the usual push:

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Use move names for algorithms and add Home corner trainer link"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, refresh and confirm **2.48.0** in the header/tab title.
Command+Shift+R can refresh the build on macOS.

Open **Method Library → 3-style corner cases**. Algorithm choices should show
the actual moves followed by their source count. Popularity order is unchanged.
On Home, **Practice** should also contain **3-style corner trainer**, which
opens the existing trainer. Its original Method Library entry remains available.

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
