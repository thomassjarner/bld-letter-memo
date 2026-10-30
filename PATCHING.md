# Update to 2.31.0

Copy the contents of `bld-letter-memo-web-2.31.0/` into your existing project,
replacing matching files and including all new files/folders. In particular,
include the new commutator finder, additional algorithm data and bundled
algorithm index in `core/`. Copy the release contents directly into
`~/Desktop/letterpairscheme-helper-web/`, rather than placing the release
folder inside it. Patching and GitHub Pages deployment are unchanged.

Run in Terminal:

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Expand algorithms and add commutator notation finder"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, reload, and confirm **2.31.0** in the header or tab title.
Command+Shift+R can refresh the build on macOS. No new package installation,
manual migration, import or storage reset is required.

## What changed

- All 332 attached algorithms were verified against their stated cycles.
  UFR algorithms and valid one-move UFR setups of the other buffers expand
  the supplied collection to all 378 UFR cases and 6,508 execution choices.
  Earlier built-in IDs and saved preferences remain valid; personal data is
  not replaced by the new collection.
- Paste plain moves in **Edit / replace alg** or **Algorithm Explorer**, then
  press **Find commutator**. A found form is checked against the entered
  execution and the full cube effect. Press **Use this notation** to apply
  it to the editor; saving remains a separate explicit action. Both table
  entries marked "Not found" can be recovered. A short form cannot always
  be found; plain moves remain usable without commutator notation.
- **Random matching case** opens the same normal case editor with the alg
  visible, editing expanded and the field ready for input. Filters still
  apply. Ordinary browsing retains the compact cube-first layout.
- The bundled index keeps library loading fast. It is included in the
  release; ordinary users do not need to regenerate it.

Data version remains 16. Existing personal algorithms/preferences, notes,
progress/favorites, schemes, letter pairs/ratings/aliases, tracing, cycle
breaks, timer sessions/history, Progressive Memo, browser persistence and
import/export retain their behavior. Dependencies and deployment are unchanged.

## Validation

314 automated tests pass, including prior checks. New checks cover all attached
cycles, recovered notation and exact cube effects, unknown structures, bounded
search, stale results, explicit saves, random-to-editor behavior, focus/scroll
cancellation and all 765 earlier built-in IDs. The complete collection was also
checked in the Flet web Python runtime, together with editing, backups and
navigation at three viewport sizes. Live browser client rendering remains
unverified here; no deployment was performed.
