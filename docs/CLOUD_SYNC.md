# Turn on WCA sign-in for BLD Letter Memo

**You only do this once as the site owner.** The website stays at its current GitHub Pages address. GitHub hosts the trainer; a Cloudflare Worker handles WCA sign-in and a private D1 database stores the training workspaces. The site still works without either service. A normal website push by itself does not activate cloud sync.

## 1. Create the database and get your service address

Install a current Node.js LTS with npm if you do not already have it. From the Mac where you keep the repository:

```bash
cd ~/Desktop/letterpairscheme-helper-web/cloud
cp -n wrangler.example.toml wrangler.toml
npx wrangler@4 login
npx wrangler@4 d1 create bld-letter-memo
```

Sign into your own Cloudflare account in the browser. Copy the **database ID** printed by the last command. If Wrangler offers to add another binding, decline: your template already has the binding named `DB`. If that database already exists, use its ID from your D1 dashboard.

Open `cloud/wrangler.toml` in a text editor:

- Replace `replace-with-the-D1-database-ID` with that ID.
- Leave `APP_URL` as `https://thomassjarner.github.io/bld-letter-memo/` for the current site, including the trailing slash. For a fork or custom domain, use the actual address instead.
- Leave the WCA client ID placeholder for now.

Back in the same terminal, run:

```bash
npx wrangler@4 d1 execute bld-letter-memo --remote --file=./schema.sql
npx wrangler@4 deploy
```

If this is your first Worker, follow the prompt to choose a workers.dev subdomain. Copy the **HTTPS address** printed by deploy, for example `https://bld-letter-memo-sync.YOUR-SUBDOMAIN.workers.dev`. The service stays inactive until you finish step 2. Re-running the provided schema does not erase records.

## 2. Register BLD Letter Memo with the WCA

1. Open [WCA OAuth applications](https://www.worldcubeassociation.org/oauth/applications) while signed into your WCA account and register an application named **BLD Letter Memo**.
2. Set its **redirect URI** to the Worker address from step 1 **followed by `/auth/callback`**. Use the exact HTTPS address, with no trailing slash after `callback`. This field points to the Worker, not GitHub Pages.
3. If offered, select a **confidential** application. This app only requests the WCA’s basic `public` scope.
4. Put the **application/client ID** in your local `cloud/wrangler.toml`, replacing the WCA placeholder. Save the file.
5. Set the **client secret** from the same terminal:

```bash
npx wrangler@4 secret put WCA_CLIENT_SECRET
npx wrangler@4 deploy
```

Paste the secret at Wrangler’s prompt. It does **not** belong in GitHub, a frontend setting, or a chat message. Your WCA password is only entered on the WCA website.

## 3. Connect GitHub Pages

In your **bld-letter-memo** repository on GitHub, open **Settings → Secrets and variables → Actions → Variables → New repository variable**:

| Field | Value |
| --- | --- |
| Name | `BLD_SYNC_URL` |
| Value | The Worker’s public HTTPS address, **without** `/auth/callback` |

Save. Push the 2.52.0 update as usual. If the code was already pushed, go to **Actions → Deploy to GitHub Pages → Run workflow**, on `main`, to make a fresh build with that variable. There is no need for an empty commit. Removing the variable and rebuilding returns the site to local-only operation.

## 4. Try it with your own workspace

On the browser that already holds your training history, open **Settings → Account & sync**. Choose **Sign in with WCA**, approve on the WCA website, then select **Enable sync** when you return. Signing in alone never uploads local training data. You can export a JSON backup at any time.

On a second device, sign in with the same WCA account and enable sync. You should see your active scheme and its cycle breaks, words and ratings, custom algorithms, settings, timer sessions, and Progressive Memo history. To check both directions, add a solve on one device and select **Sync now** on the other.

## How changes are handled

- Saves go to the browser first. Once enabled, cloud sync checks after local saves, on reopening the app or returning to it, and on Home/Settings. Sync now is also available. A failed network request does not erase or interrupt local training. If the local save itself failed, cloud sync waits.
- Separate changes combine. For two edits to the same pair, both words (and their ratings, if present) appear in Settings. Pick the version to keep; no choice is assumed. Returning to Settings compares the current copies again. Changes arriving during a solve or an edit can wait until Home or Settings so the app doesn't replace the workspace under your hands.
- New timer solves have independent IDs, even when the scramble and time are identical. Pre-2.52 backups have no IDs or dates: copies of the same session, scramble and time match by occurrence. Two identical legacy entries in one session remain two. Independently recorded, indistinguishable old entries on separate devices cannot be told apart; their dates are never guessed.
- A device session expires after 30 days. **Sign out** disconnects that browser and keeps its local data. **Delete cloud copy…** asks for confirmation, removes this app’s cloud workspace and revokes its device sessions. It does not delete the WCA account or other devices’ browser copies. Only link local training data that belongs to the account named on the screen. If the browser already holds a workspace linked to a different WCA account, sync is blocked: use its original account or a separate browser profile.
- Cloud access is restricted by the verified WCA account, including accounts without a competition ID. This is private app storage operated by the site owner; it is not end-to-end encrypted or stored in WCA competition records. Exported JSON backups never contain login credentials.
- Data is compressed before storage. If a workspace exceeds the service limit (8 MiB request or 1,750,000 compressed bytes), sync reports it and keeps the local data intact. Import/export remains available.

## Routine updates and troubleshooting

Your usual `git add`, `git commit`, `git push` flow continues to publish the website. **Only releases that change the Worker** also need `cd ~/Desktop/letterpairscheme-helper-web/cloud` and `npx wrangler@4 deploy`. Keep the untracked `cloud/wrangler.toml` on that Mac. If a later release needs a new database migration, its patching instructions should say so.

| What you see | What to check |
| --- | --- |
| “Cloud sync hasn’t been enabled for this site” | Confirm the repository **variable** is set and a fresh Pages build finished. Cloud sync is for the published browser app. |
| WCA reports an invalid redirect | Compare the registered redirect character for character with the deployed Worker address plus `/auth/callback`. |
| Sign-in could not finish | Start again from Settings in the same tab. Check the client ID, Worker secret, Worker deployment, and database schema. |
| Could not reach cloud sync | Check connectivity, Worker availability, `APP_URL`, and the database binding. Your local copy remains usable. |
| Browser save failed | Export a backup before freeing storage or changing browser settings. Do not clear site data as a first step. |

The OAuth app requests no email, date of birth, results, or competition permissions. Its server uses the numeric WCA **account** ID, and exchanges and discards the WCA access token. The session in browser IndexedDB is scoped to this trainer service. If you host untrusted JavaScript elsewhere on the same GitHub Pages **origin**, use a dedicated origin for the trainer; a URL path is not browser isolation.

References: [WCA account authorization](https://docs.worldcubeassociation.org/knowledge_base/v0_api.html), [Cloudflare D1 setup](https://developers.cloudflare.com/d1/get-started/), [Worker secrets](https://developers.cloudflare.com/workers/configuration/secrets/).
