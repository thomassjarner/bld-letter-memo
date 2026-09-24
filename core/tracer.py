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

def _canonical_transformed_sticker(sticker: str, face_map: Dict[str, str]) -> str:
    """Rename an absolute sticker into the selected memo frame.

    The scramble is always executed in the fixed White-up/Green-front frame.
    After the physical cube is rotated to the scheme's preferred orientation,
    both *positions* and *sticker identities* must be expressed in that new
    frame.  Renaming only the positions would make a solved cube appear
    scrambled under a non-standard orientation.
    """
    if len(sticker) == 1:
        return face_map[sticker]
    mapped = [face_map[c] for c in sticker]
    normal = mapped[0]
    piece_faces = set(mapped)
    order = CORNER_STICKER_ORDER if len(sticker) == 3 else EDGE_STICKER_ORDER
    for candidate in order:
        if candidate[0] == normal and set(candidate) == piece_faces:
            return candidate
    raise ScrambleError(f"Could not transform sticker {sticker}")


def _orient(state, up_color, front_color):
    """Express a scrambled state in the scheme's memo orientation.

    Scramble moves are always interpreted from White-up/Green-front.  We then
    physically rotate the finished cube so the requested center colors are on
    U/F, and finally rename every sticker relative to those centers.  This is
    the key distinction that makes alternative orientations trace correctly.
    """
    if up_color not in COLOR_FACE or front_color not in COLOR_FACE or up_color == front_color:
        raise ScrambleError("Invalid memo orientation")
    wanted_u = COLOR_FACE[up_color]
    wanted_f = COLOR_FACE[front_color]
    q = deque([state]); seen = set(); oriented = None
    while q:
        candidate = q.popleft()
        sig = tuple(_at(candidate, f) for f in "ULFRBD")
        if sig in seen:
            continue
        seen.add(sig)
        if _at(candidate, "U") == wanted_u and _at(candidate, "F") == wanted_f:
            oriented = candidate
            break
        for ax in "xyz":
            q.append(_whole(candidate, ax, 1))
    if oriented is None:
        raise ScrambleError("Up/front colors must be adjacent")

    # After the physical re-orientation, map absolute color-face identities to
    # relative U/L/F/R/B/D names using the centers now visible on each face.
    face_map = {_at(oriented, relative_face): relative_face for relative_face in "ULFRBD"}
    if set(face_map) != set("ULFRBD"):
        raise ScrambleError("Invalid center orientation")
    return {
        key: _canonical_transformed_sticker(home_sticker, face_map)
        for key, home_sticker in oriented.items()
    }


def simulate(scramble, up="W", front="G", scramble_from_own_orientation=False):
    """Simulate a scramble and return state in the scheme's memo frame.

    Normal mode reads notation in the fixed White-up/Green-front frame, then
    reframes the finished cube to the scheme orientation. Own-orientation mode
    treats U/F/R/... in the scramble as relative to the user's solving frame,
    so the relative solved state can be scrambled directly with no later reframe.
    """
    state = _solved()
    tokens = scramble.strip().split()
    if not tokens:
        raise ScrambleError("Enter a scramble first")
    for token in tokens:
        state = _apply(state, token)
    if scramble_from_own_orientation:
        # In this mode the user's own solving frame is treated as the relative
        # White-up/Green-front coordinate frame while moves are applied. Wide
        # moves in the scramble can still rotate centers, so re-center back to
        # that same relative frame before tracing.
        return _orient(state, "W", "G")
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
    # One entry per ordinary target. None means the target is not part of a
    # permutation cycle (currently used for trace/shoot twist/flip targets).
    corner_cycle_ids: List[int | None]=field(default_factory=list)
    edge_cycle_ids: List[int | None]=field(default_factory=list)
    # True for targets added specifically to memo a twist/flip in trace mode.
    corner_orientation_target_flags: List[bool]=field(default_factory=list)
    edge_orientation_target_flags: List[bool]=field(default_factory=list)
    three_style_parity_applied: bool=False

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
    if not buffer: return [], [], [], []
    buffer_piece=find_piece_for_sticker(buffer,pieces)
    if not buffer_piece: return [], [], [], []
    buffer_stickers=pieces[buffer_piece]

    # Only wrongly positioned pieces belong to permutation cycles. Correctly
    # positioned twists/flips are reserved for orientation memo.
    perm_unsolved={p for p in pieces if not _physical_correct(state,p,order)}
    targets=[]; covered=set(); cycle_ids=[]; orientation_target_flags=[]

    def add_target(sticker, cycle_id=None, orientation_target=False):
        targets.append(sticker)
        cycle_ids.append(cycle_id)
        orientation_target_flags.append(bool(orientation_target))
        p=find_piece_for_sticker(sticker,pieces)
        if p: covered.add(p)

    # Cycle numbering is based on cycles that actually contain memo targets.
    # The first visible cycle is always 0 (green in the UI), even if the
    # physical buffer cycle is empty and the first memo begins with a break.
    next_cycle_id = 0

    # Buffer cycle: stop as soon as any sticker of the physical buffer piece returns.
    cur=buffer
    buffer_cycle_started=False
    for _ in range(40):
        t=_at(state,cur)
        if t in buffer_stickers: break
        if not buffer_cycle_started:
            buffer_cycle_started=True
            current_cycle_id=next_cycle_id
            next_cycle_id += 1
        add_target(t, current_cycle_id); cur=t

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
        cycle_id = next_cycle_id
        next_cycle_id += 1
        # A cycle break shoots to the configured sticker, so that sticker is
        # itself a memo target. The cycle closes when tracing reaches the SAME
        # PHYSICAL PIECE again -- it does not have to return to the exact same
        # sticker/letter. Crucially, that closing hit IS a memo target.
        add_target(start, cycle_id)
        start_piece=piece
        cur=start
        for _ in range(40):
            t=_at(state,cur)
            t_piece=find_piece_for_sticker(t,pieces)
            add_target(t, cycle_id)
            if t_piece==start_piece:
                break
            cur=t
        else: raise ScrambleError("Cycle tracing did not close")

    # Orientation-only pieces can either be memoed visually, or converted
    # into two ordinary targets (shoot into the piece, then shoot back).
    orientation=_orientation_annotations(state,pieces,order,cat.orientation_memo)
    if cat.orientation_memo == "trace":
        for piece in _orientation_only_pieces(state,pieces,order):
            if piece == buffer_piece:
                continue
            first=preferred.get(piece,piece)
            if first not in pieces[piece]:
                first=piece
            second=_at(state,first)
            if second not in pieces[piece] or second == first:
                second=next((x for x in pieces[piece] if x != first), first)
            # These are orientation-memo targets, not another permutation cycle.
            add_target(first, None, True)
            add_target(second, None, True)
    return targets, orientation, cycle_ids, orientation_target_flags


def _memo_swap_edge_identities(state, buffer_piece: str, partner_piece: str):
    """Virtual edge memo-swap used for 3-style parity handling.

    The scrambled physical state is left untouched. Only the home identities of
    the buffer edge and configured parity-partner edge are exchanged before the
    edge trace. For DF <-> UR this also maps FD <-> RU. This deliberately flips
    edge permutation parity while preserving the normal tracing machinery.
    """
    if buffer_piece not in EDGE_PIECES or partner_piece not in EDGE_PIECES:
        raise ScrambleError("Invalid 3-style edge parity partner")
    if buffer_piece == partner_piece:
        raise ScrambleError("3-style edge parity partner must differ from the edge buffer")

    a0, a1 = buffer_piece, buffer_piece[::-1]
    b0, b1 = partner_piece, partner_piece[::-1]
    rename = {a0: b0, a1: b1, b0: a0, b1: a1}
    return {key: rename.get(home, home) for key, home in state.items()}

class ScrambleTracer:
    def trace(self, scramble: str, scheme: LetterScheme) -> TraceResult:
        state=simulate(scramble, scheme.memo_up, scheme.memo_front, scheme.scramble_from_own_orientation)

        # Corners are always traced first. In 3-style mode their parity decides
        # whether the configured edge memo-swap must be applied.
        ct,co,ccycles,cflags=_trace_category(
            state,scheme.corners,CORNER_STICKER_ORDER,CORNER_PIECES,
            STANDARD_CORNER_PRIORITY,STANDARD_CORNER_STICKER,
        )

        edge_state = state
        three_style_parity_applied = False
        if scheme.three_style_enabled and len(ct) % 2 == 1:
            buffer_sticker = scheme.edges.buffer_sticker or scheme.edges.buffer_piece
            buffer_piece = find_piece_for_sticker(buffer_sticker, EDGE_PIECES) if buffer_sticker else None
            partner = scheme.edge_parity_partner or "UR"
            if not buffer_piece:
                raise ScrambleError("Select an edge buffer before using 3-style parity handling")
            edge_state = _memo_swap_edge_identities(state, buffer_piece, partner)
            three_style_parity_applied = True

        et,eo,ecycles,eflags=_trace_category(
            edge_state,scheme.edges,EDGE_STICKER_ORDER,EDGE_PIECES,
            STANDARD_EDGE_PRIORITY,STANDARD_EDGE_STICKER,
        )

        def letters(targets,cat):
            result=[]
            for s in targets:
                v=cat.stickers.get(s,"")
                if v and v!="BUFFER": result.append(v)
                else: result.append("?")
            return result
        cl=letters(ct,scheme.corners); el=letters(et,scheme.edges)

        if three_style_parity_applied:
            # This mismatch is intentional in 3-style parity mode: corners stay
            # odd, while the virtual edge memo-swap makes the edge trace even.
            if len(et) % 2 != 0:
                raise ScrambleError(
                    "Internal 3-style trace check failed: parity-adjusted edge "
                    "memo should contain an even number of targets."
                )
        else:
            # Ordinary mode, and 3-style solves whose corner trace is even, use
            # the normal legal-cube parity invariant.
            if len(ct) % 2 != len(et) % 2:
                raise ScrambleError(
                    "Internal trace check failed: corner and edge target counts "
                    "have different parity. The memo was not shown because the "
                    "tracing result is invalid."
                )

        return TraceResult(
            ct, et, cl, el, _pair(cl), _pair(el), co, eo,
            ccycles, ecycles, cflags, eflags, three_style_parity_applied,
        )
