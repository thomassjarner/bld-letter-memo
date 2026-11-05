# Light color themes — 2.41.0

Settings → Appearance now includes a **Light color theme** selector with a small
preview. Classic Teal retains the original light appearance; Cobalt Blue,
Lavender, Warm Sand and Rose provide coordinated alternatives for surfaces,
text, accents and controls. Your choice applies immediately and is saved with
your browser data and backups. Dark mode retains its own palette.

Theme selection also reaches navigation, newly opened dialogs and text rebuilt
during algorithm playback. Cube sticker colors and user-selected rating colors
keep their existing meanings. See README for usage and PATCHING for the
unchanged update workflow.

Validation: all **566 tests pass**, including the 550 existing tests and 16 new
palette, persistence, import, contrast and control-update checks. Main semantic
text colors meet at least 4.5:1 contrast on all six surface levels in each light
palette. Web Python runtime checks pass at 1440×900 (top tabs), 1080×800
(sidebar), 390×700 (pop-out) and 280×400 (top tabs), with all five palettes,
dark/light switching, playback, walkthrough state and saved-data preservation.
Actual browser-client rendering was not measured here; no deployment was made.

# Previous UI review — 2.40.0

The review focused on finding tools quickly, keeping secondary controls out of
the working area, and using a consistent visual scale.

| Area | Improvement | Why it helps |
| --- | --- | --- |
| Main navigation | Complete page menu with the current destination on compact screens; readable single-line sidebar labels | Pages are reachable without searching a clipped horizontal tab strip; closing the menu returns keyboard focus to the active training tool |
| Sidebar | Settings stays below the scrolling destination list | Appearance and backups remain easy to find in short windows |
| Home | Direct Timer/Method Library shortcuts; smaller, balanced workflow cards with shorter copy | Returning users get to training faster and new users still see the setup sequence |
| Practice | Available modes first; planned activities in a collapsed section | The first choices are activities that can actually be used |
| Letter Schemes | Rename beside the active scheme opens a dialog; duplicate/delete icons have explicit tooltips | The main editor has more room, while management actions remain nearby |
| Letter Pairs | Mobile Filters dialog with full-width controls; rating sorting named clearly; compact readable summaries | Filters no longer become three cramped dropdowns, and more pairs remain visible |
| Scramble Memo | Shorter input block with scheme/orientation context, a setup link when needed, and diagnostics only after generation | The input and primary action are clearer, with less empty space and guidance repeated on screen |
| Method Library | Compact Workspace selector, clearer overview cards and consistent action sizing | Every section is discoverable on small screens |
| Cube viewers | Wider speed selector; hover help moved into View options | Speed labels fit better and a tooltip no longer covers the cube during study |
| Settings | Responsive appearance/playback and backup groups; compact colour/rating editor | Backups are easier to reach and the rating editor uses space more effectively |

Shared defaults use 24 px page headings, 13 px body/action text, 12 px secondary
text, 18 px action icons and 36 px regular buttons. Dense cube/list controls
retain smaller targets where their bounded layout needs them. Existing colour
roles retain light/dark contrast, and user-selected rating colours are untouched.

The Timer's display, history layout, keyboard listener and session behaviour are
retained. Progressive Memo, algorithms, commutator components, scramble tracing,
cycle breaks, schemes/pairs/aliases/ratings, persistence and import/export keep
their existing logic. Data version remains 18; no migration is needed.

## Validation

All 550 automated tests pass, including the 532 original tests and 18 new
navigation/dialog/focus regression checks. The original tests, core BLD modules,
data modules, Timer controller and Progressive Memo controller are unchanged.

Web Python runtime checks pass at 1440×900, 1080×800, 800×650, 390×700,
320×570 and 280×400, with all three navigation styles and both themes. These
checks cover destination routing, compact filters, Method Library sections,
walkthrough state, memo labels, theme colours and preservation of saved data.
They exercise Flet controls and layout calculations; actual browser-client
rendering was not measured here. No live deployment was performed.
