# Update to 2.50.0

Copy the **contents** of `bld-letter-memo-web-2.50.0/` into your existing
`~/Desktop/letterpairscheme-helper-web/`, replacing matching files. The update
process is unchanged. Include all new files and the hidden `.github/` folder,
plus the existing catalog, scripts and web-preview assets.

After extracting the ZIP into Downloads:

```bash
rsync -av ~/Downloads/bld-letter-memo-web-2.50.0/ ~/Desktop/letterpairscheme-helper-web/
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Improve timer analysis, sorting and remembered preferences"
git push
```

If the extracted folder is elsewhere, adjust the rsync source. If Git says
"nothing to commit", still push any pending local commit. Wait for GitHub
Actions, refresh and confirm **2.50.0** in the header/tab title.

On Timer, check the two analysis routes beside the current scramble, below the
last result and on history rows. Use Newest/Oldest and Fastest/Slowest in the
history footer; the expand icon shows more results. Armed 0.00 and fastest
valid times stay green in every theme. On short windows, scroll if needed to
reach both named analysis actions and the history footer.

Select your active scheme and appearance, wait for Saved, then reopen the
site. These settings should restore. No manual data migration is needed:
existing storage keys/data version 18 and import/export remain compatible.
The small workspace-preferences key is created automatically on saving.
Dependencies and deployment workflow are unchanged.

See `README.md` for behavior and `CHANGELOG.md` / `UI_CHANGES.md` for details.
