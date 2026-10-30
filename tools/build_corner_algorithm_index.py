"""Rebuild the bundled catalog after editing supplied algorithm data."""
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.algorithms import simplify_moves
from core.corner_algorithms import ALL_SUBMISSIONS, generate_algorithm_registry, _commutator_source


def build():
    seeds = {}
    for index, (position, source, comm) in enumerate(ALL_SUBMISSIONS):
        body = source.strip() if comm.strip().casefold() in ('not found.', 'not found', '') else _commutator_source(comm).strip()
        seeds.setdefault((position, body), index)
    rows = []
    for key, group in generate_algorithm_registry().items():
        seen = set()
        for algorithm in group:
            body = algorithm.alg[len(algorithm.setup) + 3:-1] if algorithm.setup else algorithm.alg
            execution = simplify_moves(algorithm.moves)
            show = execution not in seen
            seen.add(execution)
            rows.append((key, seeds[(algorithm.position, body)], algorithm.setup, show))
    digest = sha256(json.dumps(ALL_SUBMISSIONS, ensure_ascii=False).encode()).hexdigest()
    text = ('"""Verified supplied/setup catalog. Rebuild with tools/build_corner_algorithm_index.py."""\n\n'
            + f'SUBMISSIONS_SHA256 = {digest!r}\n\nALGORITHM_INDEX = (\n'
            + ''.join('    ' + repr(row) + ',\n' for row in rows) + ')\n')
    target = ROOT / 'core' / 'corner_algorithm_index.py'
    if '--check' in sys.argv:
        if not target.exists() or target.read_text() != text:
            raise SystemExit('The corner algorithm index is stale.')
    else:
        target.write_text(text)
    print(f'Verified {len(rows)} IDs; {sum(row[3] for row in rows)} menu choices across {len({row[0] for row in rows})} UFR cases.')


if __name__ == '__main__': build()
