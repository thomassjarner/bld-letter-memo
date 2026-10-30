# Update to 2.32.0

Copy the contents of `bld-letter-memo-web-2.32.0/` into your existing project,
replacing matching files and including all new files/folders. Include the new
`core/algorithm_analysis.py` and `ui/components/algorithm_converter.py` files.
Copy the contents directly into `~/Desktop/letterpairscheme-helper-web/`,
rather than placing the release folder inside it. Patching and GitHub Pages
deployment are unchanged.

Run in Terminal:

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Add linked alg converter and general playground"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, reload, and confirm **2.32.0** in the header or tab title.
Command+Shift+R can refresh the build on macOS. No new package installation,
manual migration, import or storage reset is required.

## What changed

- **Commutator** and **Final alg** are two editable linked fields in the case
  editor and Playground. Editing one updates the other automatically, without
  Find/Use steps. Comm input expands to clean moves; final moves search for a
  verified commutator. If no short form is found, final moves still work.
- **Method Library → Playground** accepts any supported algorithm independently
  of a case. It shows piece cycles, affected corners/edges, in-place twists/
  flips, detailed sticker mappings and cube reorientation, with 3D/2D playback.
- Save general algorithms with names and notes in the Playground collection.
  Reopen, update, copy or delete them. Matching UFR case routing is optional;
  saving a general alg does not modify the case library.
- Existing saved source text is preserved until explicitly saved. Case editing,
  random-to-editor behavior and normal cube-first browsing are retained.

Data version 17 automatically adds the Playground collection. Saved entries
are included in browser persistence/recovery and export/import. Import retains
its replace-all behavior and names the new collection in Settings. Existing
case algorithms/preferences, schemes, pairs/ratings/aliases, tracing, cycle
breaks, timer sessions/history and practice data remain intact. Storage keys,
dependencies, supplied algorithm IDs, playback and deployment are unchanged.

## Validation

338 automated tests pass. The Flet web Python runtime also verified linked
conversion, async cancellation, effect analysis, arbitrary-algorithm saves,
notes, migration/backups, optional case routing, themes and navigation at four
viewport sizes. Live browser client rendering remains unverified here; no
live deployment was performed.
