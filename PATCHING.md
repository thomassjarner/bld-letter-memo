# Update to 2.35.0

Copy all contents of `bld-letter-memo-web-2.35.0/` directly into your existing
`~/Desktop/letterpairscheme-helper-web/` project, replacing matching files
and including all new files. Do not put the release folder itself inside
the project. Patching and GitHub Pages deployment are unchanged.

Run in Terminal:

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Add cube switches and improve case browsing and Playground"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, reload, and confirm **2.35.0** in the header or tab title.
Command+Shift+R can refresh the build on macOS. No package installation,
manual migration, import or storage reset is required.

## What changed

- Visible **Show letters** and **Highlight pieces** switches below the cube.
  Highlighting off removes both dimming and colored outlines, in 3D and 2D.
- Stable browser panels and rows retain list position and loaded cases during
  selection. Narrow-screen browsing also retains the expanded browser and
  shared page scroll. Random case editing still focuses the alg field.
- A Playground comparison card shows the case using your selected letter
  scheme, its sticker IDs and its current preferred case algorithm. The new
  **Open case in library** button opens that saved case without replacing its
  algorithm. **Edit this alg for the case** keeps the existing draft workflow.
- The wider algorithm panel and status/notes box below the compact cube from
  2.34.0 are retained.

Data version stays 17. Existing data and saving behavior are preserved;
algorithm choices/IDs, converter, BLD logic, Timer and practice are unchanged.

## Validation

**346 automated tests pass.** The Flet web Python runtime also checked stable
browser/row identities during case selection, visible switches, letters and
highlights off in both cube views, scheme-labeled case comparison, preferred
algorithm routing, linked conversion, saving, backups and themes at six screen
sizes. Live browser client rendering remains unverified here; no deployment
was performed.

