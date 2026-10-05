# Update to 2.24.0

Copy the contents of `bld-letter-memo-web-2.24.0/` into your existing project,
replacing matching files and including the new files. Place the contents directly
in the project folder. The GitHub Pages deployment process is unchanged.

Run these commands from Terminal inside your existing project folder:

```sh
git add -A &&
git commit -m "Add optional 2D cube letter scheme editor" &&
git push
```

Wait for GitHub Actions, then reload and confirm **2.24.0** in the header or
browser-tab title. Command+Shift+R can refresh the build on macOS. Keep browser
storage; no manual data migration or import is needed.

## Use the new editor

In **Letter Schemes**, open Edges or Corners and choose **Editor → 2D cube**.
Type letters directly in that category's sticker cells. Other-category letters
remain visible; change tabs to edit them. The existing buffer dropdown selects
the exact tracing sticker and locks its entire physical piece.

Choose **Face cards** to return to the original layout. Both editors use the
same scheme data, so changes appear in either view. The chosen editor is saved
as a browser-wide UI preference. Small screens can scroll the cube horizontally
and the editor vertically.

## Preservation and validation

The new `ui/components/cube_net.py` component uses canonical sticker IDs and the
existing letter-entry callbacks. Data version 15 adds an editor preference;
older data defaults to Face cards. Tracing, scrambling, Timer, Progressive Memo,
Letter Pairs, history, repositories and storage keys are unchanged.

77 tests pass, including the existing 67 checks and new cube geometry, editor
interchange, buffer, keyboard, responsive layout, theme and backup checks.
Browser rendering remains unverified here. No live deployment was performed.
