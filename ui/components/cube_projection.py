"""Projection data shared by the native Flet cube and visual checks."""
from dataclasses import dataclass
from itertools import product
import math

from core.algorithms import move_spec
from core.cube_definitions import face_groups
from core.tracer import VEC, _at, _key
from ui.components.cube_net import FACE_COLORS, orientation_colors


@dataclass(frozen=True)
class Tile:
    points: tuple
    color: str
    label: str = ''
    foreground: str = '#FFFFFF'
    outline: str = '#0A0F0D'


def _rotate(v, axis, angle):
    c, s = math.cos(angle), math.sin(angle)
    x, y, z = v
    if axis == 'x': return x, c * y - s * z, s * y + c * z
    if axis == 'y': return c * x + s * z, y, -s * x + c * z
    return c * x - s * y, s * x + c * y, z


def _label(home, scheme, letters):
    if len(home) == 1 or not letters:
        return ''
    if set(home) == set('UFR'):
        return '★' if home == 'UFR' else '●'
    if scheme:
        cat = scheme.corners if len(home) == 3 else scheme.edges
        value = cat.stickers.get(home, '')
        if value and value != 'BUFFER':
            return value
    return home


def _style(home, scheme, involved, focus):
    colors = orientation_colors(scheme.memo_up, scheme.memo_front) if scheme else orientation_colors('W', 'G')
    color = FACE_COLORS[colors[home[0]]][0]
    if focus and involved and len(home) > 1 and frozenset(home) not in involved:
        source = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
        color = '#' + ''.join(f'{round(v * .25 + 18 * .75):02X}' for v in source)
    rgb = [int(color[i:i + 2], 16) for i in (1, 3, 5)]
    foreground = '#182B25' if sum(v * w for v, w in zip(rgb, (.2126, .7152, .0722))) > 155 else '#FFFFFF'
    return color, foreground


def project_cube(state, width, height, *, scheme=None, mode='3D', yaw=-.62, pitch=.45,
                 letters=True, focus=True, targets=(), affected=None, moving=None, fraction=0):
    involved = ({frozenset(s) for s in affected} if affected is not None else
                {frozenset(s) for s in ('UFR', *targets)} if targets else set())
    highlights = {s: color for s, color in zip(('UFR', *targets), ('#80CFC1', '#6DD8C3', '#FFD08A'))}
    if mode == '2D':
        corners, edges = dict(face_groups('corners')), dict(face_groups('edges'))
        positions = {f: (corners[f][0], edges[f][0], corners[f][1], edges[f][3], f,
                        edges[f][1], corners[f][3], edges[f][2], corners[f][2]) for f in corners}
        size = min((width - 20) / 12.7, (height - 16) / 9.5)
        gap = size * .2
        left, top = (width - (12 * size + 3 * gap)) / 2, (height - (9 * size + 2 * gap)) / 2
        tiles = []
        for face, col, row in (('U', 1, 0), ('L', 0, 1), ('F', 1, 1), ('R', 2, 1), ('B', 3, 1), ('D', 1, 2)):
            for i, sticker in enumerate(positions[face]):
                home = _at(state, sticker)
                x = left + col * (3 * size + gap) + (i % 3) * size
                y = top + row * (3 * size + gap) + (i // 3) * size
                color, fg = _style(home, scheme, involved, focus)
                tiles.append(Tile(((x + 1, y + 1), (x + size - 1, y + 1),
                                  (x + size - 1, y + size - 1), (x + 1, y + size - 1)),
                                  color, _label(home, scheme, letters), fg, highlights.get(home, '#0A0F0D')))
        return tiles

    axis, layers, quarter = move_spec(moving) if moving else ('x', (), 0)
    axis_index, angle = 'xyz'.index(axis), quarter * math.pi / 2 * fraction
    scale = min(width, height) * .285

    def view(v):
        return _rotate(_rotate(v, 'y', yaw), 'x', pitch)

    def transform(v, p):
        return view(_rotate(v, axis, angle) if p[axis_index] in layers else v)

    def face(p, normal, half, sticker=False):
        center = tuple(v * 2 / 3 + n * (1 / 3 + (.003 if sticker else 0)) for v, n in zip(p, normal))
        u = (0, 0, 1) if normal[0] else (1, 0, 0)
        v = (normal[1] * u[2] - normal[2] * u[1],
             normal[2] * u[0] - normal[0] * u[2], normal[0] * u[1] - normal[1] * u[0])
        n = transform(normal, p)
        if n[2] <= .025:
            return None
        points = [transform(tuple(c + a * half * du + b * half * dv for c, du, dv in zip(center, u, v)), p)
                  for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        depth = sum(point[2] for point in points) / 4
        screen = tuple((width / 2 + x * scale, height / 2 - y * scale) for x, y, z in points)
        return depth, screen

    painted = []
    for p in product((-1, 0, 1), repeat=3):
        for normal in VEC.values():
            geometry = face(p, normal, .326)
            if geometry:
                painted.append((geometry[0], Tile(geometry[1], '#111816')))
    for (p, normal), home in state.items():
        geometry = face(p, normal, .293, True)
        if geometry:
            color, fg = _style(home, scheme, involved, focus)
            painted.append((geometry[0] + .002, Tile(geometry[1], color, _label(home, scheme, letters), fg,
                                                   highlights.get(home, '#0A0F0D'))))
    return [tile for depth, tile in sorted(painted, key=lambda item: item[0])]
