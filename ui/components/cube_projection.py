"""Orthographic cube projection. A turning layer is one rigid solid, not 27 cubes."""
from dataclasses import dataclass
from functools import lru_cache
import math

from core.algorithms import apply_move, move_spec
from core.algorithm_playback import can_turn_together
from core.tracer import VEC, _key, _solved
from ui.components.cube_net import FACE_COLORS, face_stickers, orientation_colors

# A slightly lighter cut face keeps the turning slice legible on dark surfaces.
BODY = '#111816'
CUT = '#27312E'
RIM = '#0A0F0D'
NORMALS = tuple(VEC.values())
_HOME = _solved()
STICKERS = tuple(_HOME)
PIECES = {s: frozenset(s) for s in _HOME.values()}
_NET_FACES = face_stickers()
NET = tuple((col, row, tuple(_key(s) for s in _NET_FACES[face]))
            for face, col, row in (('U', 1, 0), ('L', 0, 1), ('F', 1, 1),
                                   ('R', 2, 1), ('B', 3, 1), ('D', 1, 2)))


@dataclass(frozen=True, slots=True)
class Tile:
    points: tuple
    color: str
    label: str = ''
    foreground: str = '#FFFFFF'
    outline: str = RIM


def _rot(v, axis, c, s):
    x, y, z = v
    if axis == 0: return x, c*y-s*z, s*y+c*z
    if axis == 1: return c*x+s*z, y, -s*x+c*z
    return c*x-s*y, s*x+c*y, z


@lru_cache(maxsize=36)
def _face_inks(up, front):
    colors = orientation_colors(up, front)
    inks = {}
    for face, key in colors.items():
        color = FACE_COLORS[key][0]
        rgb = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
        dim = tuple(round(v * .25 + 18 * .75) for v in rgb)
        for muted, fill, channels in ((False, color, rgb), (True, '#%02X%02X%02X' % dim, dim)):
            light = sum(v * w for v, w in zip(channels, (.2126, .7152, .0722))) > 155
            inks[face, muted] = fill, '#182B25' if light else '#FFFFFF'
    return inks


def _quad(center, u, v):
    return tuple(tuple(c + i*x + j*y for c, x, y in zip(center, u, v))
                 for i, j in ((-1,-1), (1,-1), (1,1), (-1,1)))


def _face_axes(normal):
    nx, ny, nz = normal
    u = (0, 0, 1) if nx else (1, 0, 0)
    v = (ny*u[2]-nz*u[1], nz*u[0]-nx*u[2], nx*u[1]-ny*u[0])
    return u, v


@lru_cache(maxsize=32)
def _block(axis, lo, hi):
    """Immutable flat faces / sticker vertices for one contiguous set of layers."""
    half = [.995] * 3
    half[axis] = (hi-lo+1)/3 - .005
    center = [0.] * 3
    center[axis] = (lo+hi)/3
    faces = []
    for normal in NORMALS:
        u, v = _face_axes(normal)
        middle = tuple(c+h*n for c, h, n in zip(center, half, normal))
        body = _quad(middle, tuple(h*x for h,x in zip(half,u)), tuple(h*x for h,x in zip(half,v)))
        stickers = []
        for key in STICKERS:
            p, n = key
            if n != normal or not lo <= p[axis] <= hi: continue
            middle = tuple(a*2/3 + b*(1/3+.003) for a,b in zip(p,n))
            stickers.append((key, _quad(middle, tuple(.293*x for x in u), tuple(.293*x for x in v))))
        inside = (normal[axis] < 0 and lo > -1) or (normal[axis] > 0 and hi < 1)
        faces.append((normal, body, CUT if inside else BODY, tuple(stickers)))
    return tuple(faces)


@lru_cache(maxsize=128)
def _turn_layers(moves):
    if not moves: return 0, ((-1, 1, 0),)
    if len(moves) > 1 and (len(moves) != 2 or not can_turn_together(*moves)):
        raise ValueError('Simultaneous playback needs two opposite outer-face turns.')
    turns = [0, 0, 0]
    for move in moves:
        axis, layers, q = move_spec(move)
        for layer in layers: turns[layer+1] = q
    blocks = []
    for layer, q in zip((-1, 0, 1), turns):
        if blocks and blocks[-1][2] == q:
            blocks[-1] = blocks[-1][0], layer, q
        else:
            blocks.append((layer, layer, q))
    return 'xyz'.index(axis), tuple(blocks)


def project_cube(state, width, height, *, scheme=None, mode='3D', yaw=-.62, pitch=.45,
                 letters=True, focus=True, targets=(), affected=None, moving=None, fraction=0,
                 edge_colors=True, buffer='UFR', highlight_stickers=None):
    involved = (affected if affected is not None else {PIECES[s] for s in (buffer, *targets)} if targets else ())
    # The public projection also accepts sticker names, as well as precomputed piece sets.
    involved = {frozenset(s) for s in involved} if focus and involved else ()
    highlights = ((highlight_stickers if highlight_stickers is not None else
                   dict(zip((buffer, *targets), ('#80CFC1', '#6DD8C3', '#FFD08A')))) if focus else {})
    inks = _face_inks(scheme.memo_up, scheme.memo_front) if scheme else _face_inks('W','G')
    buffer_piece = PIECES.get(buffer)
    def sticker(home, points):
        piece = PIECES[home]
        concealed = not edge_colors and len(home) == 2
        fill, fg = (('#35403C', '#F0F4F3') if concealed else
                    inks[home[0], bool(involved and len(home)>1 and piece not in involved)])
        label = ''
        if letters and len(home)>1 and not concealed:
            if piece == buffer_piece:
                label = '★' if home == buffer else '●'
            else:
                cat = (scheme.corners if len(home)==3 else scheme.edges) if scheme else None
                letter = cat.stickers.get(home) if cat else None
                label = letter if letter and letter != 'BUFFER' else home
        return Tile(points, fill, label, fg, highlights.get(home, RIM))

    tiles = []
    if mode == '2D':
        size = min((width-20)/12.7, (height-16)/9.5)
        gap = size*.2
        left, top = (width-(12*size+3*gap))/2, (height-(9*size+2*gap))/2
        for col, row, keys in NET:
            for i, key in enumerate(keys):
                x, y = left+col*(3*size+gap)+(i%3)*size, top+row*(3*size+gap)+(i//3)*size
                tiles.append(sticker(state[key], ((x+1,y+1),(x+size-1,y+1),
                                                  (x+size-1,y+size-1),(x+1,y+size-1))))
        return tiles

    moves = moving if isinstance(moving, tuple) else (moving,) if moving else ()
    axis, blocks = _turn_layers(moves)
    if moves and fraction in (0, 1):
        if fraction == 1:
            for move in moves: state = apply_move(state, move)
        axis, blocks = _turn_layers(())
    yc, ys, pc, ps = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    right, up, depth = (yc,0,ys), (ps*ys,pc,-ps*yc), (-pc*ys,ps,pc*yc)
    scale, ox, oy = min(width,height)*.285, width/2, height/2
    # Parallel layers never cross their separating plane. Draw the far layer
    # first, including its stickers and labels, then the nearer solid. This
    # also handles slice/wide turns and opposite outer faces turning together.
    for lo, hi, q in (blocks if depth[axis]>=0 else reversed(blocks)):
        if q:
            a = -q*math.pi/2*fraction
            c, s = math.cos(a), math.sin(a)
            r, u, d = (_rot(vec,axis,c,s) for vec in (right,up,depth))
        else:
            r,u,d = right,up,depth
        rx,ry,rz = (v*scale for v in r)
        ux,uy,uz = (-v*scale for v in u)
        def screen(vertices):
            return tuple((ox+rx*x+ry*y+rz*z, oy+ux*x+uy*y+uz*z) for x,y,z in vertices)
        visible = [(body, ink, stickers) for (nx,ny,nz),body,ink,stickers in _block(axis,lo,hi)
                   if nx*d[0]+ny*d[1]+nz*d[2] > .001]
        for body, ink, _ in visible:
            tiles.append(Tile(screen(body), ink))
        for _, _, stickers in visible:
            for key, vertices in stickers:
                tiles.append(sticker(state[key], screen(vertices)))
    return tiles
