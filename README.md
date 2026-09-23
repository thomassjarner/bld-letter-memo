# BLD Letter Memo Web 2.10

Changes:
- Letter Pairs no longer depends on scrolling: results are paged by canonical first letter (A pairs, B pairs, ...).
- Search/filtering happens before page grouping.
- Aliases stay grouped by their underlying canonical pair (for example ØB/AB stays on the A page).
- Search controls are arranged horizontally: search field on the left, both search checkboxes to its right.
- Renamed “Show letter pairs” to “Search letter pairs”.
- Letter Scheme Preferences is split into compact General / Corners tracing / Edges tracing sections.
- Corner/edge cycle-break preferences are shown in two compact columns to avoid vertical overflow.
- Buffers remain under the Edges and Corners tabs.

Regression status:
- 4/4 gold-standard scramble tests pass.


# BLD Letter Memo Web 2.9

Changes in this build:
- Letter Scheme now has three tabs: Edges, Corners, Preferences.
- Buffer selection stays inside Edges/Corners.
- Memo orientation and the former Advanced Settings content live under Preferences.
- Scheme letters automatically use uppercase.
- Pair display aliases automatically use uppercase, while mnemonic words remain exactly as typed.
- Pair alias editing only saves on Enter/blur, avoiding per-keystroke refreshes.
- Letter Pairs now uses a dedicated expanding ListView for the rows, with filters/header fixed above it.

Regression status:
- 4/4 gold-standard scramble tests pass.


# BLD Letter Memo Web 2.8

This build adds:
- explicit web scrolling for Letter Schemes and Letter Pairs;
- inline editable pair aliases on double-click;
- automatic focus advance while entering scheme letters;
- Backspace-to-previous-cell behavior for scheme entry;
- Practice keyboard shortcuts: D = DNF, + or 2 = +2;
- restored click-on-time copy for `time - scramble`;
- copy confirmation fades after 2 seconds.

The gold-standard scramble regression tests pass.


# BLD Letter Memo

A [Flet](https://flet.dev) app (desktop **and** browser, same codebase) for
managing 3x3 blindfolded (3BLD) letter schemes, a global letter-pair
mnemonic dictionary, a Scramble → Memo BLD tracing engine, and blind-solve
practice timing with Ao5/Ao12 statistics.

## Status

This is a mature, working app — see the version history at the bottom of
this file for the full feature timeline. Current major pieces:

- **Letter Schemes** — create/rename/duplicate/delete/switch schemes, exact
  buffer sticker selection, grouped sticker grid, memo orientation, and
  advanced tracing settings (cycle-break priority/stickers, twist/flip
  handling)
- **Letter Pairs** — global, searchable, inline-editable word table shared
  across all schemes
- **Scramble Memo** — full BLD tracing engine (cube simulation, orientation,
  cycle tracing with configurable cycle-breaks, twist/flip detection,
  parity check) — verified against 4 gold-standard scrambles (see
  `## Gold-standard scramble tests` below)
- **Practice** — Blind Timer with hold-to-start, Success/+2/DNF, Ao5/Ao12,
  solve history, and a shortcut from any solve to Scramble Memo
- **Settings** — dark mode, Export/Import JSON backup

## Migrated for Flet 0.86 / GitHub Pages web publishing

This project was originally built and pinned against `flet==0.24.1`
(desktop-only). It has been migrated to `flet==0.86.3` so it can be
published as a static site via `flet publish` (Pyodide-based, no server
needed) and deployed to GitHub Pages. **The migration touched only the
`ui/` layer's Flet API calls — `core/` (including the entire tracer) and
`data/` were not touched at all**, so the verified BLD engine behavior is
unchanged. Specifically:

- `ft.icons.X` / `ft.colors.X` → `ft.Icons.X` / `ft.Colors.X` (Flet renamed
  these to PascalCase after 0.24)
- `page.dialog = d; d.open = True; page.update()` → `page.open(d)` /
  `page.close(d)` (in Settings' import-confirmation dialog and Practice's
  reset-session dialog)
- `ft.app(target=main)` → `ft.run(main)`

**This migration has not been run end-to-end** (same sandbox limitation as
the original build — no network access to install Flet here). Everything
was verified with `python -m py_compile` (no syntax errors) and against
Flet's documented breaking changes, but runtime verification needs to
happen on your machine.

The Practice timer's keyboard handling (`ui/pages/practice_page.py`) was
**redesigned, not just patched**: the original background-thread/key-repeat
workaround (built around Flet 0.24 only exposing key-*down* events) crashes
outright under `flet run --web` / `flet publish`, because that runtime is
Pyodide (Python compiled to WebAssembly) and cannot create real OS threads
(`threading.Thread(...).start()` raises `can't start new thread`). Current
Flet has a proper `ft.KeyboardListener` control with real `on_key_down` /
`on_key_up` events, so the timer now uses those directly instead of
inferring release from a key-repeat stream, and all timed/delayed behavior
(arm delay, live elapsed-seconds display, copy-notice fade) runs as
`asyncio` tasks via `page.run_task(...)` instead of background threads —
`asyncio` works fine in Pyodide, real threads don't. **The one thing I
could not verify:** the exact string Flet's `KeyDownEvent.key` uses for the
spacebar. The code checks for both `"Space"` and `" "` to cover the likely
possibilities, but if holding Space does nothing at all, that's almost
certainly the culprit — tell me what (if anything) prints/happens and I can
narrow it down immediately.

## Running it

**As a desktop app** (unchanged):
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

**As a local web app** (test before publishing):
```bash
flet run --web main.py
```

**Publish as a static site** (what the GitHub Actions workflow below does
automatically on every push to `main`):
```bash
flet publish main.py --base-url /your-repo-name/
```
This writes a static site to `dist/`. `--base-url` must match your repo
name for a GitHub Pages *project* site
(`https://<username>.github.io/<repo-name>/`) — the included workflow
derives this automatically.

## Where your data lives

Schemes and words are saved to your OS's standard per-user data
directory (via `platformdirs`), **not** inside this repository:

- Linux: `~/.local/share/BLDLetterMemo/data.json`
- macOS: `~/Library/Application Support/BLDLetterMemo/data.json`
- Windows: `%APPDATA%\BLDLetterMemo\data.json`

This means pulling app updates from GitHub (or reinstalling) never
touches your saved schemes or the word dictionary. The Settings page
shows the exact path and has an "Export backup" button.

If the data file is ever unreadable (corrupted), it's copied aside as
`data.corrupt-backup.json` next to it rather than silently discarded.

## Architecture

```
core/       Pure logic, no I/O, no Flet import. Sticker/piece definitions
            and the valid-letter-pair rules live here so BLD rules can be
            refined later without touching the GUI. Also the stub for the
            future scramble tracer.
data/       Storage layer. models.py defines the data shapes; repository.py
            is an abstract interface; json_repository.py is the current
            JSON-backed implementation. Swapping to SQLite later means
            writing a new repository implementation, not touching ui/.
ui/         Flet widgets/pages. state.py is the single place pages read
            and mutate data through (every mutation autosaves).
```

### A note on the global word dictionary

Per your call: a pair like `AB` has exactly **one** word regardless of
whether it comes from a corner scheme, an edge scheme, or several
different schemes at once (`core/pairs.get_active_pairs` reports *where*
a pair is active, for display, but there's only ever one word for it).

### Known trade-offs worth knowing about

- The Letter Schemes grid does **not** rebuild itself on every keystroke
  (that would steal keyboard focus). Duplicate-letter warnings refresh
  when you switch tabs/schemes, not instantly as you type.
- The Letter Pairs table renders all matching rows at once. Flet's
  `ListView` doesn't virtualize in the classic API, so if you get into
  the high hundreds/low thousands of pairs and it feels sluggish, that's
  the place to optimize next (e.g. pagination or a virtualized list).
- `flet==0.86.3` is pinned deliberately — Flet is pre-1.0 and doesn't
  guarantee backward compatibility between releases. Bumping this pin later
  should be treated as a real migration (check Flet's changelog for
  breaking changes), not a routine dependency update.

## Deploying to GitHub Pages

`.github/workflows/deploy.yml` runs `flet publish` and deploys the result
to GitHub Pages automatically on every push to `main`. One-time setup in
the repo's settings:

1. Go to **Settings → Pages**.
2. Under **Build and deployment → Source**, choose **GitHub Actions** (not
   "Deploy from a branch").
3. Push to `main` (or run the workflow manually from the **Actions** tab).
   The site will be live at `https://<your-username>.github.io/<repo-name>/`.

## Gold-standard scramble tests

Four scrambles with hand-verified expected corner/edge memo, orientation
flags, and cycle-break behavior are the ground truth for the tracer, now
encoded as automated tests in `tests/test_gold_scrambles.py`. Run them with:

```bash
pip install -r requirements-dev.txt
pytest
```

All four currently pass (verified without pytest itself, by running the
identical assertions directly, since this sandbox has no network access to
install pytest — worth re-running properly with `pytest` on your machine).
One naming caveat is documented in the test file: gold test 1's flipped
edges are engine-labeled `FR`/`DR` rather than the hand-notes' `RF`/`RD` —
same physical edges, just a piece-naming convention difference, not a
tracing bug (see "Migrated for Flet 0.86" above).

**Do not change `core/tracer.py` without these tests passing.** If a future
change breaks one, stop and re-verify the expected memo by hand before
"fixing" the test.

## Development

The BLD-validity rules are unit-testable without any GUI dependency:

```python
from data.models import LetterScheme
from core.pairs import generate_letter_pairs, find_duplicate_letters
```

See the module docstrings in `core/pairs.py` and `core/cube_definitions.py`
for the exact rules currently implemented.

## 2.2 changes
- Buffer selection now chooses the exact buffer sticker (for example `LUB`, not just the UBL physical corner). The whole physical buffer piece remains excluded from valid letter pairs.
- Letter Pairs can be limited to one saved letter scheme.
- Duplicate mnemonic words are flagged without blocking entry.
- The saved scheme format now has forward-compatible fields for memo orientation, orientation-memo mode, preferred cycle-break stickers, and cycle-break priority. These are groundwork for the BLD tracing engine; the full editor/tracer is not enabled yet.
- Existing v1 JSON data remains loadable. A legacy piece-only buffer migrates to that piece's canonical sticker until the user explicitly chooses the exact buffer sticker.

## 2.3 experimental engine
- First working Scramble -> Memo engine: sticker-level cube simulation, standard/wide move parsing, memo-orientation normalization, buffer tracing, deterministic cycle breaks, and visual twist/flip detection.
- Scramble Memo page now accepts a scramble and shows corner/edge memo plus a diagnostic target trace.
- This is intentionally marked experimental: OP-style corner tracing matches the agreed cycle-break example; M2 edge tracing still needs method-specific refinement against the gold-standard examples before it should be trusted for real memo.


## Engine preview v2
- Cycle breaks close when tracing returns to the starting physical piece, even through a different sticker.
- The closing sticker is not added as another memo target.
- Corner and edge ordinary target-count parity is validated; orientation-only twist/flip annotations are excluded.


## 2.4 engine correction

Cycle-break closure is now piece-based **and the closing shot is retained as a memo target**.
This is required for broken cycles such as the verified examples ending in `... G`, `... P`, or `... A`.
The corner/edge target-count parity invariant remains enabled as a development safety check.

## 2.5 additions

- Scheme-level memo orientation (top/front colors), automatically used by Scramble Memo.
- Advanced per-scheme BLD settings for visual vs trace/shoot twist/flip handling.
- Per-piece preferred cycle-break sticker and reorderable cycle-break priority.
- Memo/Execution order fields with standard placeholders CE / EC; execution order controls Scramble Memo section order.
- Scramble Memo Show words / Show letters toggle; pairs without a saved word stay as letters.
- New schemes open on Edges first for faster letter entry.

## 2.6 timer preview

Practice now includes a BLD timer with persistent session solves, two-decimal
storage, Success/DNF status, Ao5/Ao12, best single, saved scrambles, and a
shortcut from a solve to Scramble Memo.

The current Flet 0.24 desktop environment does not expose key-up through the
existing global keyboard handler, so the timer infers Space release from the
OS key-repeat stream. Hold Space until READY appears, then release. Any key
stops the running timer.

Scramble generation is currently a long competition-style random-move
scramble with optional BLD orientation wide turns. The generator is isolated
so it can be replaced by a true uniform random-state solver without changing
saved solve data or the timer UI.

## 2.6.1 timer fixes

- Practice now opens to an activity menu; Blind Timer is one selectable activity.
- Blind Timer hold-to-arm behavior was reworked for Flet 0.24.1/macOS. The timer turns green when armed and starts when Space is released (inferred from the end of key-repeat events).
- Added a hidden keyboard focus sink to prevent repeated macOS alert beeps while Space is held.
- Added Success / +2 / DNF result states. +2 is included in averages and best-single calculations.
- Individual solve deletion remains available.
- Added Previous / Next scramble navigation. Going back to a scramble restores its latest saved result when available.
- The fastest successful solve in the session is highlighted in green.
- Times continue to be persisted as centiseconds (two decimal places).

## 2.6.2 fixes
- Blind Timer now autofocuses the keyboard capture control and refocuses after the timer view mounts, so the first Space hold should arm the timer without a preliminary tap.
- While the timer is running, any keyboard key stops it.
- "Take to Scramble Memo" now uses the same central navigation path as the sidebar and switches the visible page as well as the selected tab.
- Click a saved scramble to copy the scramble.
- Click a saved time to copy `time - scramble`.
- Advanced Letter Scheme tracing settings stay expanded when a setting change rebuilds the page.

## 2.6.3 fixes
- Blind Timer Space handling now uses the focused input sink itself for the initial Space press and repeats. This is intended to make the first held Space arm immediately on macOS/Flet 0.24.1 while still avoiding the alert beep. Any keyboard key stops a running timer.
- Session-history scrambles are dedicated click targets for copying only the scramble; clicking the time copies `time - scramble`.
- Copy confirmations use a separate notice that remains for about three seconds and then fades away, without overwriting timer status text.
- Letter Scheme keeps one persistent scrollable body mounted, so edits inside Advanced settings no longer rebuild the entire scroll container and jump back to the top.
- Added a persistent Dark mode switch under Settings > General. Dark mode uses a muted teal accent while Flet supplies the dark surfaces and light text automatically.

## 2.6.4 timer + twist cleanup

- Blind Timer no longer shows instructional hold-Space text. The timer itself turning green is the ready cue.
- A stopped result remains visible while browsing to the next scramble; it resets to green `0.00` only when the next solve is armed.
- The timer area is taller and less cramped.
- Corner twist `+` / `-` is now defined geometrically instead of being calibrated from a single example: the sign is the direction the corner must be twisted to solve it when viewed directly from outside the cube toward its centre (`+` clockwise, `-` counter-clockwise).
- Scramble generation is intentionally unchanged from 2.6.3.

## Flet 0.86 migration + GitHub Pages publishing

- Migrated from `flet==0.24.1` (desktop-only) to `flet==0.86.3` so the app
  can be published as a static site via `flet publish` and deployed to
  GitHub Pages. Only `ui/` API calls changed (icon/color casing, dialog
  API, app entry point) — `core/` and `data/` are untouched.
- Added `.github/workflows/deploy.yml`: publishes and deploys to GitHub
  Pages automatically on every push to `main`.
- Added `tests/test_gold_scrambles.py`: the four gold-standard scrambles
  are now automated tests (target counts, twist/flip detection, parity,
  and — for test 2 — the exact cycle-break stickers), run with `pytest`.
- Not yet verified at runtime (this sandbox can't install Flet) — see the
  "Migrated for Flet 0.86" section above for what to test first, especially
  the Practice timer's keyboard handling.

## Fix: threading crash under Pyodide ("can't start new thread")

The first real-world test of the web build hit `RuntimeError: can't start
new thread` — Pyodide (the WebAssembly Python runtime `flet run`/`flet
publish` use) cannot create OS threads at all. Root-caused to three
`threading.Thread(...)` calls in the Practice timer. Fixed by redesigning
the timer's keyboard handling around `ft.KeyboardListener`'s real
`on_key_down`/`on_key_up` events (not available when this app was first
built against Flet 0.24) and `page.run_task`/`asyncio` for all delayed/timed
behavior. Also fixed, found only by testing: `ft.Dropdown`'s `on_change` →
`on_select`, and `ft.padding`/`ft.border`/`ft.alignment` module functions →
`ft.Padding`/`ft.Border`/`ft.Alignment` classmethods.

