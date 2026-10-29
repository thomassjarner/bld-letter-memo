# Update to 2.27.0

Copy the contents of `bld-letter-memo-web-2.27.0/` into your existing project,
replacing matching files and including all new files/folders. Put the contents
directly in the project folder. Patching and GitHub Pages deployment are unchanged.

Run these commands separately in Terminal inside your existing project:

```bash
git add -A
git commit -m "Add UFR case library and algorithm learning"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, reload, and confirm **2.27.0** in the header or tab title.
Command+Shift+R can refresh the build on macOS. No new package installation,
manual data migration, import or storage reset is required.

## Use the new feature

Open **Practice → Learn → Case Library**.

- The library uses **UFR** as a fixed corner buffer, independent of your existing
  scheme's tracing buffer. The label-scheme picker does not switch the global
  active scheme. Targets without assigned letters use sticker IDs.
- Browse all **378 cases** in U/U, U/D, D/U and D/D subsets. The layers refer
  to the target pieces, in memo order. Filter by first target, status, favorites
  or search text. Scroll and More cases make every result accessible.
- Each case has a verified **generated starter**, not a curated optimal alg.
  Use the 3D/2D player to inspect it. Choose another saved alternative or paste
  your own, Preview, then Save as new/Update selected. Validation checks the
  exact target order and restoration of other pieces before saving/preference.
- Set learning status, favorites, preferred alternatives and notes. Notes save
  on leaving their field. Random matching case hides the alg and resets playback.
- **Algorithm Explorer** accepts face/wide/slice moves, rotations, groups and
  commutators. It starts solved and reports the final effect. Matching pure
  UFR cases can be opened in the library and saved as personal alternatives.
- **Commutator lesson** walks through A, B, undo A and undo B. The player includes
  stage playback, speeds, stepping, camera dragging, letter and focus toggles.

Data version 16 adds the case library automatically. Existing schemes, letter
pairs/ratings/aliases, timer sessions/history, Progressive Memo history,
preferences and browser storage keys are preserved. The existing tracer,
focused generators, Timer layout and other activities are unchanged. Backups
include the new library; import still replaces all current data as described
in Settings. Dependencies and the deployment workflow are unchanged.

## Validation

233 automated tests pass, including all previous tests. All 378 generated
starters are checked against the existing tracer. New tests cover notation,
validation, alternatives, preferences, old backups, recovery, buffer scope,
filtering/pagination, drafts/notes, themes, responsive scrolling, animated
geometry and cancellation. The Flet web Python runtime also checks the full
catalog, notation, backup round-trip and Learn controls in wide/narrow layouts.
Projected cube frames were visually inspected. Live browser/client rendering
remains unverified here; no live deployment was performed.
