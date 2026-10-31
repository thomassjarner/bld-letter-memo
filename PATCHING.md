# Update to 2.38.0

Copy all contents of `bld-letter-memo-web-2.38.0/` directly into your existing
`~/Desktop/letterpairscheme-helper-web/` project. Replace matching files and
include every new file, especially `core/walkthrough_details.py`. Do not put
the release folder itself inside the project. The update process is unchanged.

Run in Terminal:

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Improve scramble walkthrough playback and algorithm cards"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local
commit. Wait for GitHub Actions, reload and confirm **2.38.0** in the header or
tab title. Command+Shift+R can refresh the build on macOS. No installation,
manual import, data migration or storage reset is required.

## Changes

- Renamed **Corner walkthrough** to **Scramble walkthrough**, including Timer
  shortcut tooltips, the Method Library tab and overview.
- Highlight only the three physical corner pieces affected by the current
  algorithm. The original buffer piece has no permanent highlight.
- Pause between algorithms by default, keeping the completed algorithm in view.
  Continue when ready, or turn off **Pause between algs** for continuous playback.
- Algorithm cards include exact commutator notation when available, cleaned
  moves, move and quarter-turn counts, rotation counts, subset and learning
  status. Pair titles and **Open case & edit alg** lead to the exact algorithm
  alternative. A back arrow returns to the walkthrough.
- **Show solved edges** swaps the configured edge buffer and parity helper when
  corner parity is odd. The real scramble and stored preferences are unchanged.
- Leave corner twists untouched in both visual and letter memo modes. Twist
  targets are omitted before pairing, and the last ordinary odd target remains
  reserved for a separate parity algorithm. Remaining twists are shown clearly.

Data version stays **18**. Original tracing, scheme/pair data, ratings, aliases,
temporary cycle-break overrides, algorithm libraries, timers, practice history,
browser persistence and import/export retain their behavior.

## Validation

**485 automated tests pass**, including all original gold tests. The Flet web
Python runtime also checks routing, layout bounds, paused execution, case-editor
return, parity edge display, untouched twists, themes and unchanged data at six
screen sizes. Actual browser-client rendering is not measured here. No live
deployment is performed by this release package.
