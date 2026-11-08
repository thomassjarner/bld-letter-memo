# Update to 2.45.0

Copy all contents of `bld-letter-memo-web-2.45.0/` into your existing
`~/Desktop/letterpairscheme-helper-web/` project, replacing matching files.
Do not put the release folder itself inside the project.

**This update includes a deployment change:** copy the hidden `.github/`
folder too, along with `scripts/` and `web_preview/`. The workflow adds the
link-preview metadata and artwork after Flet publishes the app. Finder can
hide `.github`; Command+Shift+. shows hidden files.

If you extracted the ZIP into Downloads, this terminal command copies all
contents, including `.github`, without deleting anything from your project:

```bash
rsync -av ~/Downloads/bld-letter-memo-web-2.45.0/ ~/Desktop/letterpairscheme-helper-web/
```

Adjust the source path if you extracted it elsewhere. Then use the usual push:

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Improve link previews and verify scheme cycle-break preferences"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, refresh and confirm **2.45.0** in the header/tab title.
Command+Shift+R can refresh the build on macOS.

The deployment log should include **Add branded link preview and app icons**.
The published HTML will contain the new title, description, image and canonical
URL. An older shared message may continue to show its cached card; check a newly
shared link after deployment. No manual command on the hosted site is needed.

Progressive Memo already uses the active scheme's ordered cycle-break choices
and preferred stickers. New regression tests verify this for corners/edges,
3-style parity and scheme changes. Each attempt retains its starting scheme;
edits and scheme switches apply on the next Start.

No dependency or storage-key changes are required. Data version remains 18,
with the existing optional constraint preferences/attempt metadata. Old
backups import normally, and existing scores/times are unchanged.
The existing BLD logic, data, algorithms, temporary cycle breaks,
timer/practice histories, persistence and import/export are preserved.

See `UI_CHANGES.md` for the UI review and `CHANGELOG.md` for release history.
