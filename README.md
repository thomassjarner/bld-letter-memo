# BLD Letter Memo

A compact training workspace for blindfolded 3×3 Rubik’s Cube solving.
Build a letter scheme and pair dictionary, train memo, time solves, trace
scrambles and study algorithms. Built with Python and Flet; runs in a browser
or as a desktop app. Current version: **2.39.0**.

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
  in the Playground and watch a Scramble walkthrough.
- **Practice** — train Progressive Memo with real scrambles, typed recall,
  accuracy feedback and saved attempts. Blind Timer is also accessible here.
- **Timer** — a dedicated destination with sessions, history, averages and
  full-cube, edges-only and corners-only training.
- **Settings** — themes, playback preferences, browser-data management and
  backup import/export.

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
