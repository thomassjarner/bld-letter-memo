# Update to 2.29.0

Copy the contents of `bld-letter-memo-web-2.29.0/` into your existing project,
replacing matching files and including all new files/folders. In particular,
include `core/corner_algorithm_seeds.py` and `core/corner_algorithms.py`.
Put the contents directly in `~/Desktop/letterpairscheme-helper-web/`, rather
than placing the release folder inside it. Patching and deployment are unchanged.

Run in Terminal:

```bash
cd ~/Desktop/letterpairscheme-helper-web
git add -A
git commit -m "Add supplied commutators and second-target search"
git push
```

If Git says "nothing to commit", still run `git push` for a pending local commit.
Wait for GitHub Actions, reload, and confirm **2.29.0** in the header or tab title.
Command+Shift+R can refresh the build on macOS. No new package installation,
manual data migration, import or storage reset is required.

## What changed

- **Method Library → Case Library** has an optional **Second target sticker**
  filter. Both targets can be selected independently; together they identify
  an ordered case. Subset, status, favorite and text filters still apply.
- The 38 supplied algorithms were verified. The 34 UFR algorithms are included
  directly; the four UFL algorithms contribute valid UFR setup variants.
  Supplied algorithms and their distinct one-move outer/wide setup variants
  provide 765 alternatives covering 251 UFR cases. Remaining cases have a
  generated fallback. Direct supplied algorithms take priority, then shorter
  setup variants. Your saved preferred algorithms stay selected.
- **Fw / Fw' / Fw2** and **f / f' / f2** work in the editor, viewer and setup
  choices. The supplied **setup:[A,B]** shorthand can be pasted directly.
- The editor is above the cube. Paste an alg and choose **Save & use my alg**
  to validate, save and make it preferred in one action. **Save changes & use**
  edits a selected personal alg; **Save as another alternative** keeps both.
  **Use selected alg** can also remember a built-in alternative. The overview
  and case editor explicitly state that built-ins may not be optimal.

Data version remains 16. Personal algorithms/preferences/progress/notes/favorites,
schemes, pairs/ratings/aliases, tracer behavior, temporary cycle-break overrides,
focused scrambles, Timer sessions/history, Progressive Memo, browser persistence
and import/export retain their behavior. No data is reset or automatically
replaced by the built-in collection. Dependencies, navigation, smooth playback
and the deployment workflow are preserved.

## Validation

268 automated tests pass, including all previous checks. New checks cover all
38 supplied cycles and commutators, every valid one-move setup, 765 UFR
alternatives against the original tracer, wide-turn playback geometry, second
target filtering, replacement saves, preference preservation, backup reloads,
and bounded setup shorthand. The Flet web Python runtime independently checked
the collection, replacement flow, backups, navigation and smooth playback.
Live browser client rendering remains unverified here; no deployment was performed.
