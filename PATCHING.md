# Update to 2.34.0

Copy all contents of `bld-letter-memo-web-2.34.0/` directly into your existing
`~/Desktop/letterpairscheme-helper-web/` project, replacing matching files.
Do not put the release folder itself inside the project. Patching and GitHub
Pages deployment are unchanged.

Run in Terminal:

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Rebalance cube and algorithm workspace"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, reload, and confirm **2.34.0** in the header or tab title.
Command+Shift+R can refresh the build on macOS. No package installation,
manual migration, import or storage reset is required.

## What changed

- Wider right-hand algorithm panel, keeping alternatives, linked fields and
  preview/save/copy/delete actions together.
- Learning status and case notes move to a separate box below the cube on
  wide screens. The cube uses a narrower column and a shorter canvas.
- Cube playback and view controls stay beside the algorithm editor, with
  independent scrolling. Secondary algorithm actions use fewer rows.
- Narrow screens retain a scrollable cube-first layout, followed by editing
  and then the status/notes box. The editor remains open.

Data version stays 17. Existing data and saving behavior are preserved;
algorithm choices/IDs, converter, animation, Timer and practice are unchanged.

## Validation

**338 automated tests pass.** The Flet web Python runtime also verified the
wider algorithm pane, status/notes below the compact cube, viewport bounds,
independent scrolling, status and notes persistence, linked conversion,
Playground saves, backups, navigation and themes at six screen sizes. Live
browser client rendering remains unverified here; no deployment was performed.

