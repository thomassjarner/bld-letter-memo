# Update to 2.33.0

Copy all contents of `bld-letter-memo-web-2.33.0/` directly into your existing
`~/Desktop/letterpairscheme-helper-web/` project, replacing matching files.
Do not put the release folder itself inside the project. Patching and GitHub
Pages deployment are unchanged.

Run in Terminal:

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Simplify Method Library navigation and case editing"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, reload, and confirm **2.33.0** in the header or tab title.
Command+Shift+R can refresh the build on macOS. No package installation,
manual migration, import or storage reset is required.

## What changed

- **Edit / replace alg** is always open, with no dropdown arrow or extra click.
  The cube remains first, with independent editing scroll space on wide screens.
- **Learning status** is three small checkboxes: New, Learning and Learned.
  Exactly one is selected at a time; the existing saved status is preserved.
- **Browse UFR cases** is now **3-style corner cases**, also used in the section
  tab. The Method Library overview has two clear routes: corner cases and
  Algorithm Playground. Subset selection remains inside the case library.
- Removed the overview's **Jump to a subset** section and **Learn the basics**
  card. The existing lesson remains available from the Commutator Lesson tab.

Data version remains 17. Existing user data, supplied algorithm choices and
IDs, BLD logic, converter, animation, Timer and practice behavior are unchanged.

## Validation

338 automated tests pass. The Flet web Python runtime checked navigation,
exclusive persistent status checkmarks, always-open editing, cube bounds,
linked conversion, Playground saves, backups and themes at four screen sizes.
Live browser client rendering remains unverified here; no deployment was
performed.
