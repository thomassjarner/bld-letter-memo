# Update to 2.51.0

The update process is unchanged. Extract the ZIP into Downloads. Copy its
**contents** into your existing checkout, including new files and the hidden
`.github/` directory, then commit and push:

```bash
rsync -av ~/Downloads/bld-letter-memo-web-2.51.0/ ~/Desktop/letterpairscheme-helper-web/ &&
cd ~/Desktop/letterpairscheme-helper-web &&
git add -A &&
git commit -m "Smooth cube interaction and streamline case study and practice" &&
git push
```

If your extracted folder is elsewhere, adjust the first path. If Git reports
“nothing to commit” but your local branch has an earlier unpushed commit,
run `git push` from the checkout. When GitHub Actions finishes, refresh the
site and check **2.51.0** in the header or tab title.

Open a case in Method Library, drag the cube, use **Go to move**, and try
**Reset view**. Practice now includes **Open corner trainer**. No changes to
browser storage, your backups, or deployment settings are needed.

See [README.md](README.md) for the app guide and [CHANGELOG.md](CHANGELOG.md)
for the release history.
