"""Three-way merge of version-18 trainer workspaces. No network, UI or credentials."""
from __future__ import annotations
from core.messages import message, join_text
import hashlib
import json
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from data.models import AppData, CURRENT_VERSION

MISSING = object()


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def identify(value):
    """Name legacy history records only when participating in cloud sync."""
    result = deepcopy(value)
    for session, solves in result["practice_sessions"].items():
        seen = Counter()
        for solve in solves:
            # Include all occurrences, even ones already given an ID. Penalty
            # edits on another copy of an old backup must still match the solve.
            key = (str(solve["scramble"]), int(solve["centiseconds"]))
            seen[key] += 1
            if not solve.get("id"):
                solve["id"] = "legacy-" + _digest([session, *key, seen[key]])[:32]
    seen = Counter()
    for attempt in result["progressive_memo_history"]:
        if not attempt.get("id"):
            k = _digest(attempt); seen[k] += 1
            attempt["id"] = f"memo-{k[:32]}-{seen[k]}"
    return result


def validate(value):
    # Never silently 'upgrade' an unknown remote format by dropping fields
    # via the intentionally forgiving local backup importer.
    if not isinstance(value, dict) or value.get("version") != CURRENT_VERSION or set(value) != set(AppData().to_dict()):
        raise ValueError(message('This cloud workspace needs a different app version. Nothing was replaced.'))
    if AppData.from_dict(value).to_dict() != value:
        raise ValueError(message('The cloud workspace could not be read without changing data. Nothing was replaced.'))
    result = identify(value)
    lists = [*result["practice_sessions"].values(), result["progressive_memo_history"], result["playground_algorithms"]]
    lists.extend(row["algorithms"] for row in result["corner_case_library"].values())
    for rows in lists:
        ids = [row.get("id") for row in rows]
        if any(not isinstance(i,str) or not i for i in ids) or len(ids)!=len(set(ids)):
            raise ValueError(message('Ambiguous record IDs. Nothing was replaced.'))
    return result


@dataclass(frozen=True)
class Difference:
    path: tuple
    device: object
    cloud: object

    def key(self):
        return self.path

    @property
    def label(self):
        group = {"global_words":message('Letter pair'),"pair_aliases":message('Pair alias'),"pair_ratings":message('Pair rating'),
                 "practice_sessions":message('Timer'),"schemes":message('Letter scheme'),"playground_algorithms":message('Playground'),
                 "corner_case_library":message('Corner case'),"progressive_memo_history":message('Progressive Memo')}
        root, *rest = self.path
        head = group.get(root, message(root.replace("_", " ").capitalize()))
        fields = {"corners","edges","buffer","stickers","memo_orientation","three_style_enabled",
                  "edge_parity_partner","cycle_break_priority","cycle_break_stickers","memo_order",
                  "execution_order","tracing_mode","orientation_memo","algorithms","status","favorite",
                  "notes","preferred_algorithm"}
        path = [message(key.replace("_"," ")) if i > 0 and key in fields else str(key)
                for i, key in enumerate(rest)]
        return join_text(" · ", [head, *path])

    @staticmethod
    def describe(value):
        if value is MISSING: return message('Deleted')
        if isinstance(value,str): return value or message('(empty)')
        if isinstance(value,dict) and ("word" in value or "grade_version" in value):
            return (value.get("word") or message('(no word)')) + (message(' · rating {0:g}/5', value['rating']) if "rating" in value else "")
        if isinstance(value,dict) and "scramble" in value and "centiseconds" in value:
            return message('{0} · {1:.2f}s', value['scramble'], value['centiseconds'] / 100)+(" · DNF" if value.get("dnf") else " · +2" if value.get("plus2") else "")
        return json.dumps(value,ensure_ascii=False,sort_keys=True)


_PALETTE = ("rating_color_levels","rating_color_hexes","rating_color_grades","rating_scale_version")


def _units(snapshot):
    # Treat one word and its rating as an edit unit: a grade for an old image
    # should never be attached to a newly entered word. Likewise for a buffer's
    # physical piece and exact sticker or the interdependent palette settings.
    data=identify(snapshot)
    words=data["global_words"]; ratings=data.pop("pair_ratings"); epochs=data.pop("pair_rating_versions")
    data["global_words"]={k:{field:m[k] for field,m in (("word",words),("rating",ratings),("grade_version",epochs)) if k in m}
                           for k in set(words)|set(ratings)|set(epochs)}
    data["rating_palette"]={k:data.pop(k) for k in _PALETTE}
    for scheme in data["schemes"].values():
        scheme["memo_orientation"]=[scheme.pop("memo_up"),scheme.pop("memo_front")]
        for part in (scheme["corners"],scheme["edges"]):
            part["buffer"]=[part.pop("buffer_piece"),part.pop("buffer_sticker")]
    return data


def _unpack(data):
    data=deepcopy(data)
    records=data.pop("global_words")
    for key,field in (("global_words","word"),("pair_ratings","rating"),("pair_rating_versions","grade_version")):
        data[key]={k:row[field] for k,row in records.items() if field in row}
    data.update(data.pop("rating_palette"))
    for scheme in data["schemes"].values():
        scheme["memo_up"],scheme["memo_front"]=scheme.pop("memo_orientation")
        for part in (scheme["corners"],scheme["edges"]):
            part["buffer_piece"],part["buffer_sticker"]=part.pop("buffer")
    return data


def _keyed(path):
    return path in {("progressive_memo_history",),("playground_algorithms",)} or (
        len(path)==2 and path[0]=="practice_sessions" or
        len(path)==3 and path[0]=="corner_case_library" and path[2]=="algorithms")


def merge(base, device, cloud, choices=None):
    """Preserve independent edits; choices only apply to the exact values reviewed."""
    differences = []
    def resolve(path,b,l,r):
        if l==r: return l
        if l==b: return r
        if r==b: return l
        if _keyed(path) and isinstance(l,list) and isinstance(r,list) and (isinstance(b,list) or b is MISSING):
            source = [([] if b is MISSING else b),l,r]
            maps = []
            for items in source:
                m = {v["id"]:v for v in items}
                if len(m)!=len(items) or "" in m: raise ValueError(message('Ambiguous record IDs. No data was replaced.'))
                maps.append(m)
            bm,lm,rm = maps
            keys = dict.fromkeys([*rm,*lm])
            result = []
            for key in keys:
                item=resolve(path+(key,),bm.get(key,MISSING),lm.get(key,MISSING),rm.get(key,MISSING))
                if item is not MISSING: result.append(item)
            if path[0]=="practice_sessions":
                # Undated legacy records keep their relative order.
                result.sort(key=lambda x:(x.get("recorded_at",0),x["id"] if x.get("recorded_at") else ""))
            elif path[0]=="progressive_memo_history":
                result.sort(key=lambda x:(x.get("created_at",""),x["id"]))
            return result
        timer_row = len(path)==3 and path[0]=="practice_sessions"
        atomic = timer_row or path==("rating_palette",) or (len(path)==2 and path[0]=="global_words")
        if not atomic and isinstance(l,dict) and isinstance(r,dict) and (isinstance(b,dict) or b is MISSING):
            original = {} if b is MISSING else b
            res = {}
            for k in sorted(set(original)|set(l)|set(r)):
                child=resolve(path+(k,),original.get(k,MISSING),l.get(k,MISSING),r.get(k,MISSING))
                if child is not MISSING: res[k]=child
            return res
        diff=Difference(path,l,r)
        decision=(choices or {}).get(path)
        if decision and decision[0]==l and decision[1]==r: return l if decision[2]=="device" else r
        differences.append(diff)
        return l
    baseline=_units(base if base is not None else AppData().to_dict())
    combined=_unpack(resolve((),baseline,_units(device),_units(cloud)))
    # References to a scheme removed on the other device can't remain active.
    if combined["active_scheme"] not in combined["schemes"]:
        combined["active_scheme"]=None
    return combined,differences
