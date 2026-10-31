# Update to 2.38.1

Copy all contents of `bld-letter-memo-web-2.38.1/` directly into your existing
`~/Desktop/letterpairscheme-helper-web/` project. Replace matching files and
include the new `CHANGELOG.md`. Do not put the release folder itself inside
the project. The update process is unchanged.

Run in Terminal:

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Fix walkthrough edge preview and compact the workspace"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local
commit. Wait for GitHub Actions, reload and confirm **2.38.1** in the header or
tab title. Command+Shift+R can refresh the build on macOS.

## Changes

- Solved-edge preview swaps **UF** and your configured helper when corner
  parity is odd, regardless of the edge buffer. A UF/self or invalid helper
  uses UR for this preview. Tracing preferences remain unchanged.
- Removed routine parity and edge-swap notices. Memo and extra metadata are in
  a collapsed **Walkthrough details** section beneath the algorithm cards.
- The cube starts directly below the scramble controls and uses more of the
  available space. Playback pauses, highlighting and case-editor links remain.
- README is now a project guide. The previous README is preserved in full in
  `CHANGELOG.md`, following the current release notes.

No dependency, data-format or storage-key changes. Existing tracing, schemes,
pairs, ratings, aliases, temporary cycle breaks, algorithms, timers, training
history, persistence and import/export retain their behavior.

## Validation

501 automated tests pass, including the original BLD gold tests. Flet web
Python runtime checks also pass at six screen sizes for the fixed UF display,
compact layout, optional details, playback, editor navigation, themes and saved
data. Actual browser-client rendering is not measured here. No live deployment
is performed by this release package.
