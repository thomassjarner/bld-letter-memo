# Update to 2.52.0

Extract the ZIP into Downloads. Copy its **contents** into your existing checkout, including new files and the hidden GitHub Actions workflow:

```bash
rsync -av ~/Downloads/bld-letter-memo-web-2.52.0/ ~/Desktop/letterpairscheme-helper-web/ &&
cd ~/Desktop/letterpairscheme-helper-web &&
git add -A &&
git commit -m "Add optional WCA sign-in and cloud sync" &&
git push
```

If you already copied the files, start at `cd ~/Desktop/letterpairscheme-helper-web`. If Git says “nothing to commit” and you previously committed the update, run `git push`.

**Pushing the website still works the same way.** Without extra configuration everyone can still use local saves, export and import. To activate **Sign in with WCA**, follow the [one-time cloud setup guide](docs/CLOUD_SYNC.md). It covers the WCA registration, your private database, and the one public repository variable. Future frontend-only releases still need only your usual push. Future changes to the backend also need a Worker deploy.

Wait for the Pages action to finish, reopen the site, and check for **v2.52.0**. The current local workspace and existing backups are retained. This release does not automatically upload anyone’s data.
