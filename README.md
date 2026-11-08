# BLD Letter Memo

A compact training workspace for blindfolded 3×3 Rubik’s Cube solving.
Build a letter scheme and pair dictionary, train memo, time solves, trace
scrambles and study algorithms. Built with Python and Flet; runs in a browser
or as a desktop app. Current version: **2.45.0**.

## Workspaces

- **Home** — choose a setup, training or analysis activity.
- **Letter Schemes** — assign corner and edge letters with face cards or a 2D
  cube. Configure buffers, memo orientation and cycle-break priorities/stickers.
- **Letter Pairs** — build and rate your pair dictionary, with aliases and
  filters for focused editing.
- **Scramble Memo** — trace a real scramble using your scheme. Explore temporary
  cycle-break alternatives without changing saved preferences.
- **Method Library** — browse 378 UFR 3-style corner cases, save preferred
  algorithms, use linked move/commutator fields, explore arbitrary algorithms
  in the Playground, watch a Scramble walkthrough and train case recall.
- **Practice** — train Progressive Memo with real scrambles, typed recall,
  accuracy feedback and saved attempts. Blind Timer is also accessible here.
- **Timer** — a dedicated destination with sessions, history, averages and
  full-cube, edges-only and corners-only training.
- **Settings** — five light color themes, dark mode, playback preferences, browser-data management and
  backup import/export.

## Finding your way around

Desktop tabs keep all eight workspaces together. On compact screens, the header
shows your current page and **Open navigation** opens the complete page menu.
Sidebar and pop-out navigation remain available in Settings; their saved
preferences are retained across screen sizes.

Home has quick **Timer** and **Method Library** shortcuts plus compact cards for
the setup and training workflow. Practice shows the available activities first;
planned modes are grouped under **More practice modes**.

- **Letter Schemes:** use **Rename** beside the active scheme to edit its name
  in a dialog. Face cards, 2D cube entry order and buffer controls are unchanged.
- **Letter Pairs:** on smaller screens, **Filters** opens full-width scheme,
  status and rating controls. The main page keeps search and the pair list in
  view. Rating summaries remain explicit, and short screens put them in Filters.
- **Scramble Memo:** the input identifies the active scheme and orientation.
  First-time users get a direct setup link. Empty diagnostics stay out of the
  way until there is a trace to inspect.
- **Method Library:** compact screens use a **Workspace** selector so every
  section is reachable. Cube help lives under View options rather than hovering
  over the cube; playback controls have clearer, consistent sizes.
- **Settings:** appearance/playback and backups are grouped together, with a
  compact rating-colour editor below.

See [UI_CHANGES.md](UI_CHANGES.md) for the page-by-page UI review.

## Progressive Memo corrections

Before starting, the **Constraints** section has two saved switches:

- **Allow memo navigation** — off by default for one-pass training. Enable it
  to use Previous/Left Arrow and Next/Right Arrow during memo, including moving
  back to the preceding category before recall begins.
- **Show category overview** — on by default. Disable it to move directly from
  the final prompt to the next category title or recall without showing all
  the category's letters again.

Recall correction is always available. Both choices freeze when an attempt
starts and are recorded with its result/history. Older attempts retain the
original one-pass/overview-shown defaults. Category titles still last one
second, and revisiting memo prompts does not restart the clock.

During recall, **Previous** (to the left of Confirm) or **Left Arrow** returns
to the preceding answer, including across a category boundary. Its previous
text is selected so typing replaces it immediately. Later answers and the
current draft stay in place; confirming a correction replaces the original
answer instead of shifting the sequence.

**Right Arrow / Next** keeps the current answer and moves forward. It acts as
**Skip** only when that prompt has never had any letters. Empty edits, clearing
a selection and passing through answers cannot erase retained input: only
replacement letters overwrite it. Space/Enter also keeps a retained answer
when no new letters were typed. Late events from an old prompt are ignored.
The clock continues while correcting, and only
the final answers save when the attempt finishes. Completed results are not
editable after the correct solution has been revealed.

Recall inputs accept the number of letters in their prompt: a final single
letter uses one letter, without an unused Extra tile. Older saved attempts
keep their original scoring; additional typed letters are listed separately.

The ready screen shows whether the selected scheme has **3-style** enabled.
When enabled, the existing tracer applies its configured edge-buffer/helper
swap for odd corner parity; Progressive Memo requires complete ordinary edge
pairs. It never pads or drops a target. Without 3-style, a final single edge
letter remains valid, and corners can also finish with one letter.

Progressive Memo follows the **active letter scheme's saved cycle-break
priority order and preferred sticker for each piece**, using the same tracer
as Scramble Memo. Each Start freezes those preferences for the attempt;
switching schemes or editing their order takes effect on the next Start.
Temporary alternatives explored in Scramble Memo do not replace the scheme's
saved choices. This behavior is covered for both corners and edges, including
3-style and orientation-letter memo.

## Sharing the site

Shared links have a branded **BLD Letter Memo | Blindfold Cube Training**
title, a short feature description and a 1200×630 cube image. Browser and
installed-app icons use the matching cube mark. The metadata is in the static
HTML, so preview services can read it before the Python app starts.

The GitHub Pages workflow runs `scripts/web_metadata.py` immediately after
`flet publish`, before uploading `dist`. It derives the public URL from the
repository owner/name and preserves Flet's base path, runtime scripts and
manifest navigation. **Include the updated hidden `.github` folder when
installing this release**; see [PATCHING.md](PATCHING.md).

For a manual static build or a custom domain, run the same step with the actual
public URL after publishing:

```bash
flet publish main.py --base-url /bld-letter-memo/
python scripts/web_metadata.py --output dist --site-url https://thomassjarner.github.io/bld-letter-memo/
```

Publish uses the bundled `web_preview/` PNGs with no new dependency. Developers
can regenerate them with `python scripts/render_preview.py` if Pillow is
installed. Existing chat messages may retain a previously cached preview;
the release does not edit those messages or force external cache refreshes.

## 3-style corner trainer

Open **Method Library → Corner trainer** (or the overview's **Open corner
trainer** card). This trainer uses the same fixed **UFR buffer** case library.

1. Choose one or more target-layer subsets (U/U, U/D, D/U, D/D), optional first
   and second target stickers, and learning statuses. Target choices show your
   scheme's letters beside sticker IDs. Favorites can narrow the selection.
   The matching count updates before you start.
2. Start a session. Each matching case appears once, in shuffled order. From a
   **solved physical cube**, apply the displayed setup in your scheme's U/F
   orientation. The preview shows that case without letters or highlighting.
3. Recall and execute your algorithm. **Show alg** reveals the letter pair,
   physical targets, commutator and cleaned full moves. Valid saved preferred
   algorithms are used; invalid imported choices get a verified built-in
   fallback without changing the saved record. Some raw algs may have no
   recoverable commutator; their verified full moves are still shown.
4. Rate **Remembered** or **Missed**. The solution is then shown automatically;
   this automatic reveal does not count as a hint. Use the solution to restore
   your cube before pressing **Next case**. A reveal before rating is counted
   separately, and recall percentages are self-rated.
5. After the last case, open the summary for remembered/missed lists, recall
   rate and reveal count. Expand a result to review its alg or open its editor.
   **Retry missed cases** starts a new shuffled pass of those cases only.

Subset/status selections combine within their groups, then intersect with the
target and favorite filters. Empty selections cannot start a round. The round
freezes its scheme and algorithm choices. Navigation, theme changes, resizing,
and returning from the editor retain the current round; **End session** shows
a partial summary with **Resume session** available. Results live in the current
page session and are not added to browser backups or retained after a reload.
Recall ratings do not modify Learning/Learned labels or any existing histories.

Setups use the bundled solver via an independent route, and are checked against
the complete cube state. A verified generated setup remains available when a
native installation has no JavaScript runtime. No additional dependency is needed.

## Light color themes

Open **Settings → Appearance → Light color theme** and choose **Classic Teal**,
**Cobalt Blue**, **Lavender**, **Warm Sand**, or **Rose**. The preview shows the
selected palette. Each coordinates backgrounds, panels, text, accents and
controls across the site, including dialogs and algorithm playback.

The choice applies immediately in light mode and saves automatically. Dark
mode keeps its existing palette; returning to light restores your chosen theme.
You can also choose a light theme while dark mode is on and see it in the preview.
Cube sticker colors, memo-cycle colors, rating colors and training data are
unchanged. Backups include your selection. Older backups and first-time users
default to the original **Classic Teal** appearance.

## Run locally

Use Python **3.12**. From the project directory on macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
flet run --web main.py
```

On Windows, create the environment with `py -3.12 -m venv .venv` and activate
it with `.\.venv\Scripts\Activate.ps1` in PowerShell. Then run the same install
and Flet commands. For the desktop app, use `python main.py` instead of the
web command. Dependencies are pinned in `requirements.txt`.

## Scramble walkthrough

Open **Method Library → Scramble walkthrough**, select your scheme, paste a
scramble and generate. Playback uses your preferred verified case algorithms
and saved cycle-break choices. It pauses between algorithms by default; use
**Continue to next alg**, or turn off **Pause between algs**. Letters and
three-piece highlighting have separate switches beneath the cube.

Cards show commutators, final moves, statistics and links to the case editor.
**Walkthrough details** beneath the cards contains the memo and extra metadata.
The case editor's back arrow returns to the same walkthrough position.
Built-in algorithms are starting points; save your preferred replacements.

Corner twists are left untouched, and a final unpaired target is reserved for
your separate parity algorithm. Edge display can be hidden, solved or scrambled.
In the solved-edge preview, UF swaps with your configured helper when needed,
regardless of the edge buffer. A UF/self or invalid helper uses UR for this
preview. These display choices do not change tracing preferences or the scramble.
Timer cube icons open the current scramble or a saved solve in this workspace.

## Algorithm playback

Every Method Library cube can show commutator notation beneath the move list.
A and B use distinct colours; the current written move is underlined and
highlighted in sync with the expanded moves. During an undo section, the
highlight points to the written move being undone, while the move list shows
the actual inverse turn. A small label identifies the current component.

Choose **Components** beside the speed selector to pause after Setup, A, B,
Undo A, Undo B and Undo setup. Nested setups are separate components too.
**Continue** advances to the next complete component. Simultaneous opposite
turns stay within their component. This works in corner cases, Playground,
Commutator Lesson and Scramble walkthrough.

**Full alg** uses normal playback. Component mode follows the written notation,
so turns that combine at component boundaries in normal playback remain
separate for study. The move counter follows the selected view. Switching modes
restarts the current algorithm. Both views finish at the same cube state and
retain the saved algorithm source.

If a raw algorithm has a recoverable commutator, its verified notation is used.
An unavailable form is kept as moves; another algorithm for the same case is
never substituted to provide a commutator display.

## Saved data

The published web app stores schemes, dictionaries, preferences, algorithm
libraries and training history in that browser for that site. Use
**Settings → Export backup** and import/export controls to back up or move your
data. Desktop saves use the system's application-data directory. Application
updates retain the existing persistence format and storage keys.

## Development

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

| Folder | Purpose |
| --- | --- |
| `core/` | Cube simulation, BLD tracing, algorithms and training logic |
| `data/` | Data models, persistence and backups |
| `ui/` | Flet pages, shared controls, themes and navigation |
| `tests/` | Logic, persistence and UI-control regression tests |
| `tools/` | Maintenance and catalog utilities |

## Updates and publishing

For a downloaded release, copy the extracted folder's **contents** into your
existing project, including new files, then commit and push. Exact terminal
commands are in [PATCHING.md](PATCHING.md).

The included GitHub Actions workflow publishes `main.py` and deploys to GitHub
Pages on pushes to `main`. It derives the Pages base URL from the repository
name. For a manual static build, use
`flet publish main.py --base-url /your-repo-name/`; the output is in `dist/`.

See [CHANGELOG.md](CHANGELOG.md) for release history and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for dependency notices.
