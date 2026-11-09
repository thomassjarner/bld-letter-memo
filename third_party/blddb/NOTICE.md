# BLDDB corner algorithm snapshot

Source: [BLDDB v2](https://v2.blddb.net), **manmade** corner mode.
Repository: <https://github.com/nbwzx/blddb>, v2 branch.
Pinned revision: `f555e56d93b2f6ca503aa32ad0f3bd93a6938ce5`.
Retrieved: **2026-11-09**.

Credit goes to BLDDB's maintainers, Zixing Wang / nbwzx, and the cubers whose
public algorithm sheets are attributed in its database. Source names and
sheet URLs are retained in `core/blddb_corner_catalog.json`; each case in the
app links back to BLDDB. Popularity means the number of source sheets in a
BLDDB group, not measured execution speed or a guarantee of optimality.

Files under `upstream/` are unmodified copies from that exact revision:

- `public/data/cornerManmade.json`: original all-buffer corner data.
- `public/data/sourceToUrl.json`: original source attribution links.
- `src/utils/codeConverter.ts`: sticker/code mappings and equivalent-cycle rules.
- `src/components/Table/index.tsx`: source-count sorting and variant presentation.
- `README.md` and `LICENSE`: upstream description and full GNU GPL v3 license.

These upstream files and the derived catalog retain BLDDB's
**GPL-3.0-or-later** license. See [upstream/LICENSE](upstream/LICENSE).
Full source and the deterministic transformation script are included in this
release. No BLDDB JavaScript is executed by the app or by the importer.

`tools/import_blddb_corners.py` reads the public literal sticker mappings,
finds the equivalent canonical cycle for each UFR case, uses a stable
descending source-count sort, and preserves spellings within each group.
Every move sequence is verified as the exact pure UFR corner cycle. Supplied
commutators must also match the actual execution and full cube effect.

The compiled catalog contains **378 UFR cases**, **2,252 popularity groups**
and **2,423 algorithm spellings**. Its metadata records every input SHA-256.
It is an offline snapshot; the web app does not fetch changes in the background.

Reproduce and validate the catalog from the vendored source:

```bash
python tools/import_blddb_corners.py --check
```

To fetch the same pinned snapshot again and rebuild, use `--download`.
For a reviewed future revision, explicitly supply its full commit SHA and
snapshot date, then run the tests before deploying.
