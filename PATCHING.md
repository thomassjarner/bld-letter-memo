# Update to 2.59.0: Simplified Chinese

Merge the contents of the extracted release into your existing Desktop repository
(using Finder’s **Merge** for folders). Keep your existing .git directory, Pages
workflow and local Worker configuration. The new **assets/fonts** folder contains
the interface font and its license. From the updated Desktop repository:

```bash
cd ~/Desktop/letterpairscheme-helper-web &&
git add -- assets core data ui web_cloud scripts/cloud_build.py tools/subset_hans_font.py tests docs/LOCALIZATION.md README.md THIRD_PARTY_NOTICES.md CHANGELOG.md UI_CHANGES.md PATCHING.md &&
git commit -m "Add Simplified Chinese to the training workspace" &&
git push origin main
```

After Pages deploys, choose **Settings → General → Language / 语言 → 简体中文**.
No Worker deployment or database migration is needed for this release.

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
