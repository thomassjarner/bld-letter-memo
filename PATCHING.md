# Update to 2.23.0

Copy the contents of `bld-letter-memo-web-2.23.0/` into your existing project
folder, replacing matching files and including the new files. Place the contents
directly in your project. The normal GitHub Pages deployment process is unchanged.

Run these commands from Terminal inside your existing project folder:

```sh
git add -A &&
git commit -m "Add Progressive Memo practice with recall scoring and history" &&
git push
```

Wait for GitHub Actions, then reload and confirm **2.23.0** in the header or
browser-tab title. Command+Shift+R can refresh the build on macOS. Keep browser
storage. Existing browser data is read with the same storage keys; the new
practice history is an additive data field.

## Use Progressive Memo

Open **Practice → Progressive Memo**, choose your letter scheme, then press Start.
The activity uses your Memo and Exec settings from Letter Schemes. Start shows
the first memo category for one second; the clock starts with its first letters.
Space advances ordinary pairs, grouped letter-based twists/flips, then the full
category review. The next category has the same one-second title and sequence.
Visual twists/flips are omitted. After the final review, Space starts recall in
execution order. Type each pair, single final letter or entire orientation group
and press Space or Enter to confirm. Use Skip for an answer you cannot remember.

After the last answer, inspect the green/red comparison tiles, correct solution,
accuracy and total/memo/recall times. The result and scramble save automatically.
Select a history row to reopen it; Older attempts loads more saved records.
Cancel, Back or navigation away discards an unfinished attempt.

## Preservation and validation

The approved Timer and Letter Pairs pages are unchanged, as are existing tracing,
scramble generation, scheme models, timer records and AppState methods. New
modules provide Progressive Memo and the Practice hub. Data version 14 adds
separate practice history to browser storage and backups. Existing version-13
backups import with empty Progressive Memo history and their original data.

67 tests pass, including original BLD, Timer, layout and theme checks, plus
practice sequencing, recall, accuracy, cancellation, focus, history and storage.
Browser rendering remains unverified here. No live deployment was performed.
