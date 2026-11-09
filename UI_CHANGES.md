# BLDDB corner alternatives — 2.47.0

The existing case picker now offers only the BLDDB manmade choices plus your
saved personal algorithms. The former supplied/setup/generated menu entries
are replaced. **Most popular** is the default; other choices use labels such
as **BLDDB #2.3 · 23 sources**, where 2 is the upstream popularity group and
3 is its spelling. All spellings in a group share its source-sheet count.
Ordering and ties match BLDDB's unfiltered manmade view.

The short source line shows rank, count and snapshot date. Contributor names
are available in its tooltip. A compact **BLDDB** link opens the physical
UFR/first/second case, including its original source sheet links. Existing
editor fields, cube size/layout, stage playback and custom-alg controls remain.
No new panel above the cube is introduced.

Case defaults, Playground lookup, Scramble walkthrough and trainer now use
the same new catalog. Personal algs and their preferences remain. Retired
builtin IDs are preserved in backup data and fall back to the new default
without being reintroduced into the menu. Notes, statuses, favorites and
training/session data are not migrated or reset.

The 2026-11-09 offline snapshot contains **378 cases**, **2,252 groups** and
**2,423 spellings**. Each spelling solves its stated exact pure corner cycle.
Notation, where supplied, is checked against both its full cube effect and
actual execution signature. Snapshot provenance, source credit, license and
a reproducible importer are included in the release.

Validation: **691 tests pass**, including 15 new checks. All 2,423 variants
also pass cube verification in the web Python runtime. At 1440×900, 1080×800,
390×700 and 280×400, the ranked picker/source links serialize correctly,
component and full playback retain the same final state, and default/personal
selection, walkthrough/trainer integration and saved-data preservation pass.
Popularity order, ties and spellings were independently checked on the live
UFR–UBL–UBR and UFR–LDB–FDL BLDDB pages. App browser-client layout was not
measured; no live deployment was performed.

# Grouped Home and feature icons — 2.46.0

Home now has four sections with two feature rows each:

| Section | Links |
| --- | --- |
| Set up your memo | Set up your letter scheme; Build your letter pairs |
| Analyze a scramble | Scramble Memo; Scramble walkthrough |
| Learning material | Method Library; Algorithm Playground |
| Practice | Blind Timer; Progressive Memo |

Each row has one compact icon badge, a readable feature name, a short
description and a trailing arrow. The entire row is a focusable button, with
a theme-aware focus background. Category headings separate intent from the
individual tool names. The smaller introduction and two-column category grid
keep the desktop page compact; phones get one scrolling column and taller
rows for wrapping text.

The Home Method Library entry opens its overview. Walkthrough and Playground
open their exact Method Library sections, and Progressive Memo opens directly
in Practice. Their original entry points remain. Timer keeps its top-level
destination and existing control/session. The shortcuts do not create duplicate
tool instances or change the existing behavior when leaving an unfinished
training attempt.

The main feature icons use original native line drawings: lettered cards for
pairs/memo, a target route for Scramble Memo, a cube/play mark for walkthrough,
a book for Method Library and a stopwatch for Timer. Small warm accents work
with the current palette. The same glyphs appear in the top tabs, compact
menu/sidebar/pop-out and Practice/Method Library cards. Every paint follows
semantic theme roles; no external image assets or dependencies are used.

Validation: **676 tests pass**, including 21 new checks of grouping, direct
and original routes, reused tool controls, existing training navigation
behavior and reversible icon colors/contrast. Three older tests were updated
for the new Home entry layout. Web Python checks pass in 24 configurations:
five light themes plus dark mode at 1440×900, 1080×800, 390×700 and 280×400,
covering all navigation styles. Native Canvas icons also serialize correctly
at small sizes and were visually inspected from their actual primitives.
Actual browser-client layout was not measured; no live deployment was performed.

# Shared-link preview and scheme verification — 2.45.0

Shared links use a proper site title, a concise training description and a
1200×630 dark/mint cube graphic. The matching cube mark appears as the browser
favicon and installed-app icon. These assets and metadata are added to the
static build, where preview services can read them without starting Flet.
There is no change to in-app layouts or saved preferences.

Progressive Memo is confirmed to use the active scheme's saved cycle-break
order and preferred stickers. The existing tracer and attempt snapshots are
retained. New tests check the actual chosen piece/sticker, resulting letters,
scheme switching and priority edits on the next Start, with and without 3-style.

The release includes a new post-publish workflow step; the hidden `.github`
folder is part of the update. See PATCHING.md for a copy command that includes it.

Validation: **655 tests pass**, including 23 new metadata/active-scheme checks.
The Flet 0.86.3 published HTML template keeps its startup scripts and base path
unchanged after processing. The PNG artwork was visually inspected. No live
deployment or external chat-card rendering was performed.

# Progressive Memo constraints and safe review — 2.44.0

Right Arrow is now forward navigation that retains an entered answer, with
Skip only for a prompt without any letters. Empty changes and submissions
cannot replace saved text. Only replacement letters overwrite it. Recall
inputs belong to a specific prompt visit, so a delayed event from an old input
cannot clear or submit another answer.

Before Start, **Constraints** offers **Allow memo navigation** and **Show
category overview**. Defaults preserve one-pass memo with a category review.
Enabling navigation adds Previous/Next and arrow shortcuts during memo;
disabling overview omits the final display of all the category's letters.
The original timer continues through revisits, and stale intro tasks are ignored.

Choices are saved as optional preferences and frozen in each attempt's result.
Old histories keep their prior defaults and scores. Recall correction remains
available regardless of the memo navigation constraint.

Validation: **632 tests pass**, including 22 new checks. The reported pair-4
correction is tested with retained pairs 5 and 6, along with empty edits, stale
input callbacks, forward review, all constraint combinations, empty categories,
intro timing, settings/backup defaults and per-attempt metadata. One existing
test's destructive Right Arrow expectation was corrected; other existing test
files are unchanged. Web Python runtime checks pass at 1440×900, 1080×800,
390×700 and 280×400 for every constraint combination and all navigation styles.
Actual browser keyboard/focus rendering was not measured here; no deployment
was performed.

# Progressive Memo corrections — 2.43.0

Recall has Previous / Confirm / Skip in that order, with Left Arrow and Right
Arrow shortcuts. Going back restores and selects the previous input. Confirm
overwrites that answer in place, while later answers/drafts remain available.
Selection tasks are tied to the current prompt revision to avoid selecting a
newly typed draft after a delayed focus event.

Single-letter prompts accept only one letter. Results no longer show an Extra
tile beside that expected letter. Genuine additional input in older saved
attempts is reported as text, with their existing scores preserved.

The ready view explicitly shows the scheme's 3-style status. The original
tracer's configured buffer/helper parity swap is retained, with a complete-pair
check in Progressive Memo. Corners and non-3-style edges can retain their final
single letter. No targets are fabricated or discarded to adjust parity.

Validation: **610 tests pass**, including 20 new checks for in-place correction,
draft retention, arrow keys, selected replacement, Unicode, held Space, parity,
single-letter feedback and unchanged histories. All previous tests, the tracer,
stored data models and the timer/Method Library implementations are unchanged.
Web Python runtime checks pass at 1440×900, 1080×800, 390×700 and 280×400, using
all navigation styles and both modes. Actual browser keyboard/selection
rendering was not measured here; no deployment was performed.

# Corner recall trainer — 2.42.0

Method Library has a new **Corner trainer** section and overview card. Filter
case layers/statuses with checkboxes, select letter-labelled targets, then run
one shuffled pass. Setups and solutions are verified on the entire cube.

The setup and cube appear first. Targets and algorithms remain hidden until
Show alg or rating. Remembered/Missed records only once; Next case is separate
so there is time to solve the physical cube before another setup. The summary
groups misses and successes, counts reveals and offers Retry missed cases.
The case editor has a return button to preserve your training position.

The layout scrolls at compact sizes and uses the existing light palettes and
dark mode. Session choices/results are local to this page session; existing
learning statuses and saved training data are not rewritten. See README for
the complete flow and PATCHING for the unchanged update process.

Validation: **590 automated tests pass**, including 24 new trainer checks. The
378-case portable setup route is verified on the complete cube; the bundled
solver is also exercised directly. Web Python runtime checks pass at 1440×900
(top tabs), 1080×700 (sidebar), 390×700 (pop-out) and 280×400 (top tabs), including
12 real web-solver setups, hidden answers, summary/retry, navigation and themes.
Navigation expectations in two existing test files now include the sixth
section/card; other existing test files and all previous core/data modules are unchanged.
Actual browser-client rendering was not measured here; no deployment was made.

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
