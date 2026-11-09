"""Verified BLDDB manmade UFR algorithms, in upstream popularity order.

Code-owned choices never enter the user's saved records. Legacy builtin IDs
remain round-trippable in backups, but are not offered or executed as defaults.
Personal algorithms and their explicit preferences still take precedence.
"""
from dataclasses import dataclass
from functools import cached_property, lru_cache
from hashlib import sha256
import json
from pathlib import Path

from core.algorithms import parse_algorithm
from core.corner_cases import corner_cases


QUALITY_NOTICE = ('BLDDB manmade algorithms · ranked by source count. '
                  'Popularity does not guarantee an optimal alg; you can save your own.')
CATALOG_PATH = Path(__file__).with_name('blddb_corner_catalog.json')


def case_source_url(key):
    case = corner_cases()[key]
    return f'https://v2.blddb.net/corner?position=UFR-{case.first}-{case.second}&mode=manmade'


@dataclass(frozen=True)
class BuiltinAlgorithm:
    id: str
    name: str
    alg: str
    origin: str
    position: str
    source_count: int
    rank: int
    variant: int
    variant_count: int
    raw_alg: str
    commutator: str
    sources: tuple[str, ...]

    @cached_property
    def moves(self):
        return parse_algorithm(self.alg).moves

    @property
    def source_url(self):
        return 'https://v2.blddb.net/corner?position=' + self.position + '&mode=manmade'


@lru_cache(maxsize=1)
def _snapshot():
    data = json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
    if (data.get('schema') != 1 or data['metadata'].get('buffer') != 'UFR'
            or set(data['cases']) != set(corner_cases())):
        raise ValueError('The bundled BLDDB UFR catalog is incomplete or incompatible.')
    return data


def catalog_metadata():
    return dict(_snapshot()['metadata'])


@lru_cache(maxsize=1)
def blddb_case_algorithms():
    result = {}
    for key, entry in _snapshot()['cases'].items():
        variants = []
        previous_count = float('inf')
        for rank, group in enumerate(entry['groups'], 1):
            sources = tuple(group['sources'])
            if not sources or len(sources) > previous_count:
                raise ValueError(f'Invalid BLDDB popularity order: {key}')
            previous_count = len(sources)
            count = len(group['variants'])
            for index, item in enumerate(group['variants'], 1):
                # Rank/source count are deliberately absent from the ID: a
                # saved choice survives later popularity changes.
                identifier = 'builtin:blddb:' + sha256((key + '\n' + item['moves']).encode()).hexdigest()[:24]
                name = item['moves'] + f' · {len(sources)} ' + ('source' if len(sources) == 1 else 'sources')
                variants.append(BuiltinAlgorithm(
                    identifier, name, item['source'], 'blddb', 'UFR-' + key.replace(':', '-'),
                    len(sources), rank, index, count, item['moves'], item['commutator'], sources))
        if not variants:
            raise ValueError(f'No BLDDB alternatives for {key}')
        result[key] = tuple(variants)
    return result


def builtin_algorithms(key):
    return blddb_case_algorithms()[key]


def display_builtin_algorithms(key, retained=()):
    # Old supplied/setup/generated choices never reappear through a retained
    # legacy preference. The original preference is left untouched in backups.
    return builtin_algorithms(key)
