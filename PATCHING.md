# Update to 2.49.0

Copy all contents of `bld-letter-memo-web-2.49.0/` into your existing
`~/Desktop/letterpairscheme-helper-web/` project, replacing matching files.
Do not put the release folder itself inside the project.

The copy/commit/push process is unchanged. Include the new
`ui/commutator_editing.py` and `tests/test_commutator_editing.py` files, as well
as all matching updates. Keep the bundled BLDDB catalog/attribution and the
hidden `.github/`, `scripts/` and `web_preview/` folders used for deployment.
Finder can show hidden files with Command+Shift+.

If you extracted the ZIP into Downloads, copy its contents with:

```bash
rsync -av ~/Downloads/bld-letter-memo-web-2.49.0/ ~/Desktop/letterpairscheme-helper-web/
```

Adjust the source path if you extracted it elsewhere. Then use the usual push:

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Add automatic brackets to commutator editing"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, refresh and confirm **2.49.0** in the header/tab title.
Command+Shift+R can refresh the build on macOS.

In **Method Library → 3-style corner cases** or **Playground**, clear the
Commutator field. It should show `[]`. Type `R: U, D` inside it: the result
should be `[R: [U, D]]`, and Final alg should update. Complete pasted
commutators retain their pairs. In Final alg, a move sequence without a short
commutator match remains usable while the Commutator field shows `[]`.

No dependency or storage-key changes are required. Data version remains 18.
The bundled BLDDB ranking, personal algs, schemes/pairs, cycle-break priorities,
temporary overrides, memo/timer/trainer history, preferences, browser persistence
and import/export are unchanged.

See `README.md` for usage, `UI_CHANGES.md` for the editing behavior and
`CHANGELOG.md` for release history.
