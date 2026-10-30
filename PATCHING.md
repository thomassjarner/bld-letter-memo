# Update to 2.36.0

Copy all contents of `bld-letter-memo-web-2.36.0/` directly into your existing
`~/Desktop/letterpairscheme-helper-web/` project, replacing matching files and
including every new file. Include `core/algorithm_playback.py`. Do not put the
release folder itself inside the project. Patching and GitHub Pages deployment
are unchanged.

Run in Terminal:

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Add optional simultaneous opposite-face playback"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, reload, and confirm **2.36.0** in the header or tab title.
Command+Shift+R can refresh the build on macOS. No package installation,
manual migration, import or storage reset is required.

## What changed

- New **Settings → Algorithm playback → Simultaneous moves** switch, off by
  default. Consecutive opposite outer-face turns play together and appear as
  `(U D')` in the cube's move caption. U/D, R/L and F/B support all primes
  and double-turn combinations.
- Next/previous buttons step through a simultaneous pair together. Move counts
  and exact cube results remain unchanged. Original commutator-stage boundaries
  and explicit partial playback endpoints remain separate.
- Saved algorithms and editable converter fields are unchanged. This only
  affects visualization and playback. Existing letters/highlight switches,
  browser scroll preservation, compact layout and Playground comparison remain.

Data version 18 adds the saved preference, including export/import and browser
persistence. Old data defaults to off. Existing application data and the
original BLD tracing, Timer and practice logic retain their behavior.

## Validation

**364 automated tests pass.** Checks cover all 54 combinations of opposite
face order and prime/double direction, exact combined-turn geometry, grouped
captions and steps, cancellation, stage boundaries, partial endpoints, old-data
migration, backup import and the Settings switch. Prior case browsing,
comparison, data and training checks are retained. The Flet web Python runtime
also checked the preference, geometry/endpoints, old-data migration, navigation,
conversion, saving/backups and themes at six screen sizes. Live browser client
rendering remains unverified here; no deployment was performed.

