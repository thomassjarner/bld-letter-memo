"""Rebuild the offline UFR catalog from the pinned BLDDB manmade snapshot.

From the project folder:
    python tools/import_blddb_corners.py --check
    python tools/import_blddb_corners.py --download

Only --download accesses the network. To refresh, explicitly pass a reviewed
40-character --revision and --snapshot-date YYYY-MM-DD with --download.
Upstream files, license, attribution and exact input hashes are retained.
"""
from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.algorithms import normalized_state, parse_algorithm
from core.commutator_finder import execution_signature
from core.corner_cases import corner_cases, identify_case_state

REVISION = 'f555e56d93b2f6ca503aa32ad0f3bd93a6938ce5'
SNAPSHOT_DATE = '2026-11-09'
UPSTREAM = ROOT / 'third_party/blddb/upstream'
TARGET = ROOT / 'core/blddb_corner_catalog.json'
FILES = ('public/data/cornerManmade.json', 'public/data/sourceToUrl.json',
         'src/utils/codeConverter.ts', 'src/components/Table/index.tsx', 'LICENSE', 'README.md')


def download(revision, source_root=UPSTREAM):
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Use an exact reviewed 40-character upstream commit, not a mutable branch.')
    for name in FILES:
        url = f'https://raw.githubusercontent.com/nbwzx/blddb/{revision}/{name}'
        request = urllib.request.Request(url, headers={'User-Agent': 'BLD-Letter-Memo-catalog-import'})
        with urllib.request.urlopen(request, timeout=45) as response:
            content = response.read()
        path = source_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def _maps(source):
    # Read only literal public mapping data; never evaluate upstream code.
    letters = re.search(r'Chichu:\s*"([^"]+)"', source).group(1)
    positions = re.search(r'const positionArray\s*=\s*(\[[\s\S]*?\]);', source).group(1)
    following = re.search(r'const nextPositionsMap\s*=\s*({[\s\S]*?});', source).group(1)
    positions = json.loads(re.sub(r',\s*]', ']', positions))
    following = json.loads(re.sub(r',\s*}', '}', following))
    if len(positions) != len(letters):
        raise ValueError('Upstream sticker mapping changed; review the importer.')
    return dict(zip(positions, letters)), following


def _query_keys(positions, letters, following):
    variants = []
    for _ in range(3):
        code = ''.join(letters[position] for position in positions)
        variants.extend(code[index:] + code[:index] for index in range(3))
        positions = [following[position] for position in positions]
    return variants


def _notation(text):
    text = text.strip()
    if text.casefold() in ('', 'not found', 'not found.'):
        return ''
    return text if text.startswith('[') else '[' + text + ']'


def build_catalog(source_root=UPSTREAM, revision=REVISION, snapshot_date=SNAPSHOT_DATE):
    date.fromisoformat(snapshot_date)
    if not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('The snapshot must identify an exact upstream commit.')
    raw = {name: (source_root / name).read_bytes() for name in FILES}
    data = json.loads(raw['public/data/cornerManmade.json'])
    source_urls = json.loads(raw['public/data/sourceToUrl.json'])
    letters, following = _maps(raw['src/utils/codeConverter.ts'].decode())
    cases, used_sources = {}, set()
    groups_count = variants_count = 0
    for key, case in corner_cases().items():
        matches = [candidate for candidate in _query_keys(['UFR', case.first, case.second], letters, following)
                   if candidate in data]
        if len(matches) != 1:
            raise ValueError(f'Expected exactly one BLDDB cycle for {key}, got {matches}')
        groups = []
        seen = set()
        # Python's stable sort also preserves upstream order for ties, as the
        # site's stable JavaScript source-count sort does with no speed filter.
        for group in sorted(data[matches[0]], key=lambda item: -len(item[1])):
            moves, sources, notations = group
            if not sources or len(moves) != len(notations):
                raise ValueError(f'Unexpected BLDDB group structure for {key}')
            variants = []
            for full, comm in zip(moves, notations):
                algorithm = parse_algorithm(full)
                if identify_case_state(normalized_state(algorithm)) != key:
                    raise ValueError(f'BLDDB algorithm does not solve {key}: {full}')
                expression = _notation(comm)
                if expression:
                    structured = parse_algorithm(expression)
                    if (execution_signature(structured.moves) != execution_signature(algorithm.moves)
                            or normalized_state(structured) != normalized_state(algorithm)):
                        raise ValueError(f'BLDDB notation does not match its actual execution: {key}')
                if full in seen:
                    raise ValueError(f'Repeated BLDDB spelling in different groups: {key}')
                seen.add(full)
                variants.append({'moves': full, 'commutator': comm,
                                 'source': expression or full})
            used_sources.update(sources)
            groups.append({'sources': sources, 'variants': variants})
            variants_count += len(variants)
        groups_count += len(groups)
        cases[key] = {'upstream_key': matches[0], 'groups': groups}
    attribution = {}
    for name in sorted(used_sources):
        urls = source_urls.get(name, {})
        attribution[name] = urls.get('corner') or urls.get('3bld') or urls.get('bld') or ''
    return {
        'schema': 1,
        'metadata': {
            'name': 'BLDDB', 'mode': 'manmade', 'buffer': 'UFR',
            'website': 'https://v2.blddb.net', 'repository': 'https://github.com/nbwzx/blddb',
            'revision': revision, 'snapshot_date': snapshot_date, 'license': 'GPL-3.0-or-later',
            'input_sha256': {name: sha256(content).hexdigest() for name, content in raw.items()},
            'cases': len(cases), 'groups': groups_count, 'variants': variants_count,
            'source_sheets': attribution,
        },
        'cases': cases,
    }


def render_catalog(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--revision', default=REVISION)
    parser.add_argument('--snapshot-date', default=SNAPSHOT_DATE)
    args = parser.parse_args()
    if args.download:
        download(args.revision)
    result = build_catalog(revision=args.revision, snapshot_date=args.snapshot_date)
    text = render_catalog(result)
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding='utf-8') != text:
            raise SystemExit('The BLDDB catalog is stale; rebuild and review it.')
    else:
        TARGET.write_text(text, encoding='utf-8')
    meta = result['metadata']
    print(f'Verified {meta["variants"]} variants in {meta["groups"]} popularity groups across {meta["cases"]} UFR cases.')


if __name__ == '__main__':
    main()
