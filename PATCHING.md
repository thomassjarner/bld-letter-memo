# Update to 2.58.0: successful solve times in the timer overview

Use the existing Git repository on your Desktop. Merge the updated **core**,
**ui** and **tests** folders and the four Markdown files from the extracted
release into `~/Desktop/letterpairscheme-helper-web`. Keep your local
configuration, including `cloud/wrangler.toml`. If the updated files are
already there, run this directly:

```bash
cd ~/Desktop/letterpairscheme-helper-web &&
git add -- core ui tests README.md CHANGELOG.md UI_CHANGES.md PATCHING.md &&
{ git diff --cached --quiet || git commit -m "Show mean and median successful solve times in the timer overview"; } &&
git push origin main
```

After GitHub Pages deploys, open **Blind Timer → Statistics** or **Progressive
Memo → Statistics**. Existing solves and synced data work immediately. This
update does not change the Pages workflow, Worker or database.

## Previous update: 2.52.1 WCA return repair (only if still on the old Worker)

The existing 2.52.0 website works with the corrected Worker. If your sign-in button was already visible, deploying the Worker is enough to repair this issue. Keep your current `cloud/wrangler.toml`, Cloudflare secret, D1 database and GitHub variable.

## Quick repair on your Mac

Save the standalone **bld-wca-signin-fix.mjs** download to Downloads, then paste:

```bash
cd ~/Desktop/letterpairscheme-helper-web/cloud &&
cp ~/Downloads/bld-wca-signin-fix.mjs worker/index.mjs &&
npx wrangler@4 deploy --config wrangler.toml
```

When Wrangler prints **Deployed bld-letter-memo-sync triggers**, go to the trainer in your normal browser. Start from **Settings → Account & sync → Sign in with WCA**. Complete the login in the same tab. Choose **Enable sync** if you want to link this browser’s training data. On an error, share only the short reference shown on the page.

To keep the single-file repair in GitHub for future deploys:

```bash
cd ~/Desktop/letterpairscheme-helper-web &&
git add -- cloud/worker/index.mjs &&
git commit -m "Fix WCA sign-in on Cloudflare Workers" -- cloud/worker/index.mjs &&
git push
```

## If you prefer the full project ZIP

Extract the ZIP and copy the **contents** of `bld-letter-memo-web-2.52.1` into your existing checkout. If you extracted it in Downloads, you can use this command. It preserves your local configuration:

```bash
rsync -av --exclude='.git/' --exclude='cloud/wrangler.toml' --exclude='.dev.vars*' \
  ~/Downloads/bld-letter-memo-web-2.52.1/ ~/Desktop/letterpairscheme-helper-web/
```

The full release includes the tests and documentation. For the live sign-in repair, run the Worker deploy from `cloud/` as above (skip the single-file copy if you copied the full release). Commit and push the website files as usual when ready. This update does not change the Pages workflow, backup format or database schema. For a new installation see [cloud setup](docs/CLOUD_SYNC.md).
