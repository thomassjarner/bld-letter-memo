"""Rebuild the local UI font after changing Chinese copy (development only).

Usage: python tools/subset_hans_font.py path/to/NotoSansCJK-Regular.ttc --index 2
Requires fontTools. No font processing, downloads or installs are needed to run the site.
"""
import argparse
from pathlib import Path
from runpy import run_path

ROOT = Path(__file__).resolve().parents[1]


def main():
    from fontTools import subset
    from fontTools.ttLib import TTFont
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("font")
    parser.add_argument("--index", type=int, default=2)
    args = parser.parse_args()
    font = TTFont(args.font, fontNumber=args.index, recalcTimestamp=False)
    if font["name"].getDebugName(1) != "Noto Sans CJK SC":
        parser.error("Choose the Simplified Chinese face of Noto Sans CJK.")
    copy = run_path(str(ROOT / "core/zh_cn.py"))["MESSAGES"].values()
    # Include the endonym, notation punctuation, and printable Latin range.
    wanted = set("".join(copy) + "简体中文") | {chr(i) for i in range(32, 127)}
    options = subset.Options()
    sub = subset.Subsetter(options=options)
    sub.populate(text="".join(sorted(wanted)))
    sub.subset(font)
    names = {1:"BLD Memo Hans", 2:"Regular", 3:"BLDMemoHans-Regular-1",
             4:"BLD Memo Hans Regular", 6:"BLDMemoHans-Regular"}
    for rec in font["name"].names:
        if rec.nameID in names:
            rec.string = names[rec.nameID].encode(rec.getEncoding())
    cff = font["CFF "].cff
    cff.fontNames[0] = names[6]
    cff.topDictIndex[0].FamilyName, cff.topDictIndex[0].FullName = names[1], names[4]
    out = ROOT / "assets/fonts/bld-memo-hans.otf"
    out.parent.mkdir(exist_ok=True, parents=True)
    font.save(out)


if __name__ == "__main__":
    main()
