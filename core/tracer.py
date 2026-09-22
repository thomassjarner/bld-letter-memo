"""Experimental 3x3 scramble -> BLD memo engine.

The cube simulator is deliberately separate from BLD tracing.  It applies
face/wide moves to labelled stickers, then re-orients the finished cube to
the scheme's memo orientation before tracing permutation cycles.
"""
from dataclasses import dataclass, field
from collections import deque
import re
from typing import Dict, List, Tuple

from core.cube_definitions import CORNER_STICKER_ORDER, EDGE_STICKER_ORDER, CORNER_PIECES, EDGE_PIECES, find_piece_for_sticker
from data.models import LetterScheme

Vec = Tuple[int, int, int]
Key = Tuple[Vec, Vec]
VEC = {"R":(1,0,0),"L":(-1,0,0),"U":(0,1,0),"D":(0,-1,0),"F":(0,0,1),"B":(0,0,-1)}
FACE_COLORS = {"U":"W","D":"Y","F":"G","B":"B","R":"R","L":"O"}
COLOR_FACE = {v:k for k,v in FACE_COLORS.items()}
MOVES = {"R":("x",1,-1),"L":("x",-1,1),"U":("y",1,-1),"D":("y",-1,1),"F":("z",1,-1),"B":("z",-1,1)}
TOKEN = re.compile(r"^([URFDLB])([w]?)(2|'|2')?$")

# Standard preset: intentionally simple and editable later.  The first entries
# match the user's OP/M2 preferences established during engine design.
STANDARD_CORNER_PRIORITY = ["DFR","DFL","UFR","UFL","UBR","DBR","DBL","UBL"]
STANDARD_EDGE_PRIORITY = ["UB","DR","DL","FR","FL","UR","UL","DB","BR","BL","UF","DF"]
STANDARD_CORNER_STICKER = {p:p for p in CORNER_PIECES}
STANDARD_EDGE_STICKER = {p:p for p in EDGE_PIECES}

class ScrambleError(ValueError): pass

def _add(vs): return tuple(sum(v[i] for v in vs) for i in range(3))
def _rot(v:Vec, axis:str, q:int)->Vec:
    x,y,z=v
    for _ in range(q%4):
        if axis=="x": x,y,z=x,-z,y
        elif axis=="y": x,y,z=z,y,-x
        else: x,y,z=-y,x,z
    return x,y,z

def _key(sticker:str)->Key:
    return (_add([VEC[c] for c in set(sticker)]), VEC[sticker[0]])

def _solved()->Dict[Key,str]:
    result={}
    for s in CORNER_STICKER_ORDER+EDGE_STICKER_ORDER+list("ULFRBD"):
        result[_key(s)]=s
    return result

def _at(state, sticker): return state[_key(sticker)]

def _apply(state, token):
    m=TOKEN.match(token)
    if not m: raise ScrambleError(f"Unsupported move: {token}")
    face,wide,suffix=m.groups(); axis,layer,clock=MOVES[face]
    amount=2 if suffix and suffix.startswith("2") else (-1 if suffix=="'" else 1)
    q=clock*amount; ai={"x":0,"y":1,"z":2}[axis]
    out={}
    for (p,n),home in state.items():
        selected=p[ai]==layer or (wide and p[ai] in (layer,0))
        if selected: p,n=_rot(p,axis,q),_rot(n,axis,q)
        out[(p,n)]=home
    return out

def _whole(state, axis, q):
    return {(_rot(p,axis,q),_rot(n,axis,q)):h for (p,n),h in state.items()}

def _orient(state, up_color, front_color):
    if up_color not in COLOR_FACE or front_color not in COLOR_FACE or up_color==front_color:
        raise ScrambleError("Invalid memo orientation")
    wanted_u=COLOR_FACE[up_color]; wanted_f=COLOR_FACE[front_color]
    q=deque([state]); seen=set()
    while q:
        s=q.popleft(); sig=tuple(_at(s,f) for f in "ULFRBD")
        if sig in seen: continue
        seen.add(sig)
        if _at(s,"U")==wanted_u and _at(s,"F")==wanted_f: return s
        for ax in "xyz": q.append(_whole(s,ax,1))
    raise ScrambleError("Up/front colors must be adjacent")

def simulate(scramble, up="W", front="G"):
    state=_solved()
    tokens=scramble.strip().split()
    if not tokens: raise ScrambleError("Enter a scramble first")
    for token in tokens: state=_apply(state, token)
    return _orient(state, up, front)

@dataclass
class TraceResult:
    corner_targets: List[str]
    edge_targets: List[str]
    corner_letters: List[str]
    edge_letters: List[str]
    corner_pairs: List[str]
    edge_pairs: List[str]
    corner_orientation: List[str]=field(default_factory=list)
    edge_orientation: List[str]=field(default_factory=list)

    @property
    def corner_memo(self): return " ".join(self.corner_pairs + self.corner_orientation)
    @property
    def edge_memo(self): return " ".join(self.edge_pairs + self.edge_orientation)

def _pair(letters): return ["".join(letters[i:i+2]) for i in range(0,len(letters),2)]

def _physical_correct(state, piece, order):
    stickers=[s for s in order if set(s)==set(piece)]
    return all(set(_at(state,s))==set(piece) for s in stickers)

def _orientation_only_pieces(state, pieces, order):
    """Pieces in the correct physical slot but with wrong orientation."""
    out=[]
    for piece in pieces:
        if not _physical_correct(state,piece,order):
            continue
        stickers=[s for s in order if set(s)==set(piece)]
        if all(_at(state,s)==s for s in stickers):
            continue
        out.append(piece)
    return out

def _dot(a: Vec, b: Vec) -> int:
    return sum(x*y for x,y in zip(a,b))

def _cross(a: Vec, b: Vec) -> Vec:
    return (
        a[1]*b[2]-a[2]*b[1],
        a[2]*b[0]-a[0]*b[2],
        a[0]*b[1]-a[1]*b[0],
    )

def _corner_twist_sign(state, piece: str, stickers) -> str:
    """Return + / - using a geometric, position-independent definition.

    The sign describes the *correction needed to solve the corner*: look
    directly at that corner from outside the cube toward the centre. ``+``
    means the corner must be twisted 120 degrees clockwise to solve it; ``-``
    means 120 degrees counter-clockwise. This avoids face-dependent special
    cases and matches the established gold examples (DBR+, UFR+, DFL-).
    """
    # Canonical corner names always begin on U or D. Track that reference
    # sticker and find the face on which it currently sits.
    reference_face = piece[0]
    current_face = None
    for position_sticker in stickers:
        occupant = _at(state, position_sticker)
        if occupant[0] == reference_face:
            current_face = position_sticker[0]
            break

    if current_face is None or current_face == reference_face:
        # Defensive fallback; orientation-only callers should never reach this.
        return "+"

    outward_axis = _add([VEC[c] for c in set(piece)])
    current_vec = VEC[current_face]
    solved_vec = VEC[reference_face]

    # Viewed from outside toward the cube centre, a clockwise correction has
    # a negative oriented triple product around the outward corner diagonal.
    turn = _dot(outward_axis, _cross(current_vec, solved_vec))
    return "+" if turn < 0 else "-"

def _orientation_annotations(state, pieces, order, mode):
    if mode != "visual": return []
    out=[]
    for piece in _orientation_only_pieces(state,pieces,order):
        if len(piece)==2:
            out.append(f"({piece}#)")
        else:
            sign = _corner_twist_sign(state, piece, pieces[piece])
            out.append(f"({piece}{sign})")
    return out

def _trace_category(state, cat, order, pieces, standard_priority, standard_stickers):
    buffer=cat.buffer_sticker or cat.buffer_piece
    if not buffer: return [], []
    buffer_piece=find_piece_for_sticker(buffer,pieces)
    if not buffer_piece: return [], []
    buffer_stickers=pieces[buffer_piece]

    # Only wrongly positioned pieces belong to permutation cycles. Correctly
    # positioned twists/flips are reserved for orientation memo.
    perm_unsolved={p for p in pieces if not _physical_correct(state,p,order)}
    targets=[]; covered=set()

    def add_target(sticker):
        targets.append(sticker)
        p=find_piece_for_sticker(sticker,pieces)
        if p: covered.add(p)

    # Buffer cycle: stop as soon as any sticker of the physical buffer piece returns.
    cur=buffer
    for _ in range(40):
        t=_at(state,cur)
        if t in buffer_stickers: break
        add_target(t); cur=t

    priority=cat.cycle_break_priority if cat.cycle_break_priority else standard_priority
    preferred=dict(standard_stickers); preferred.update(cat.cycle_break_stickers)
    while True:
        remaining=[p for p in priority if p in perm_unsolved and p not in covered and p!=buffer_piece]
        if not remaining:
            # Safety fallback for a custom priority list that omitted a piece.
            remaining=[p for p in pieces if p in perm_unsolved and p not in covered and p!=buffer_piece]
        if not remaining: break
        piece=remaining[0]; start=preferred.get(piece,piece)
        if start not in pieces[piece]: start=piece
        # A cycle break shoots to the configured sticker, so that sticker is
        # itself a memo target. The cycle closes when tracing reaches the SAME
        # PHYSICAL PIECE again -- it does not have to return to the exact same
        # sticker/letter. Crucially, that closing hit IS a memo target: it is
        # the final shot that closes the broken cycle.
        add_target(start)
        start_piece=piece
        cur=start
        for _ in range(40):
            t=_at(state,cur)
            t_piece=find_piece_for_sticker(t,pieces)
            add_target(t)
            if t_piece==start_piece:
                break
            cur=t
        else: raise ScrambleError("Cycle tracing did not close")

    # Orientation-only pieces can either be memoed visually, or converted
    # into two ordinary targets (shoot into the piece, then shoot back).
    # The preferred cycle-break sticker is also the preferred first sticker
    # for this trace/shoot representation.
    orientation=_orientation_annotations(state,pieces,order,cat.orientation_memo)
    if cat.orientation_memo == "trace":
        for piece in _orientation_only_pieces(state,pieces,order):
            # A twisted/flipped buffer is not memoed as its own orientation
            # target in trace/shoot mode.  The buffer is already the tracing
            # origin; if it is physically in place but misoriented, tracing
            # simply starts a new cycle at the highest-priority eligible
            # non-buffer piece.  The non-buffer orientation-only pieces below
            # are handled as ordinary shoot/out-and-back targets.
            if piece == buffer_piece:
                continue
            first=preferred.get(piece,piece)
            if first not in pieces[piece]:
                first=piece
            second=_at(state,first)
            if second not in pieces[piece] or second == first:
                # Defensive fallback: choose another sticker on the same piece.
                second=next((x for x in pieces[piece] if x != first), first)
            add_target(first)
            add_target(second)
    return targets, orientation

class ScrambleTracer:
    def trace(self, scramble: str, scheme: LetterScheme) -> TraceResult:
        state=simulate(scramble, scheme.memo_up, scheme.memo_front)
        ct,co=_trace_category(state,scheme.corners,CORNER_STICKER_ORDER,CORNER_PIECES,STANDARD_CORNER_PRIORITY,STANDARD_CORNER_STICKER)
        et,eo=_trace_category(state,scheme.edges,EDGE_STICKER_ORDER,EDGE_PIECES,STANDARD_EDGE_PRIORITY,STANDARD_EDGE_STICKER)
        def letters(targets,cat):
            result=[]
            for s in targets:
                v=cat.stickers.get(s,"")
                if v and v!="BUFFER": result.append(v)
                else: result.append("?")
            return result
        cl=letters(ct,scheme.corners); el=letters(et,scheme.edges)

        # A legal 3x3 permutation has matching corner/edge permutation parity.
        # Visual twist/flip annotations are orientation-only and deliberately
        # do not participate in this check. If this fails, the trace is wrong;
        # never "repair" the memo by adding/removing a target.
        if len(ct) % 2 != len(et) % 2:
            raise ScrambleError(
                "Internal trace check failed: corner and edge target counts "
                "have different parity. The memo was not shown because the "
                "tracing result is invalid."
            )

        return TraceResult(ct,et,cl,el,_pair(cl),_pair(el),co,eo)
