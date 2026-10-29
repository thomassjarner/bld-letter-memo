"""Learning notation must agree with existing moves and bound expansion."""
import pytest

from core.algorithms import algorithm_states, inverse_moves, normalized_state, parse_algorithm
from core.tracer import _apply, _solved


def final(source):
    return algorithm_states(parse_algorithm(source))[-1]


@pytest.mark.parametrize('face', list('URFDLB'))
@pytest.mark.parametrize('suffix', ['', "'", '2'])
@pytest.mark.parametrize('wide', ['', 'w'])
def test_face_and_wide_moves_match_the_unchanged_scramble_simulator(face, suffix, wide):
    move = face + wide + suffix
    assert final(move) == _apply(_solved(), move)


@pytest.mark.parametrize('a,b', [
    ('x', "R M' L'"), ('y', "U E' D'"), ('z', "F S B'"),
    ('Rw', "R M'"), ('Lw', 'L M'), ('Uw', "U E'"),
    ('Dw', 'D E'), ('Fw', 'F S'), ('Bw', "B S'"), ('r2', 'Rw2'),
])
def test_slice_rotation_and_lowercase_notation_have_the_expected_geometry(a, b):
    assert final(a) == final(b)


def test_commutators_conjugates_repeats_inverse_and_stage_boundaries():
    alg = parse_algorithm("[F: [R, U' L' U]]")
    assert alg.expanded == "F R U' L' U R' U' L U F'"
    assert [s.label for s in alg.stages] == ['Setup', 'A', 'B', 'Undo A', 'Undo B', 'Undo setup']
    assert [(s.start, s.end) for s in alg.stages] == [(0, 1), (1, 2), (2, 5), (5, 6), (6, 9), (9, 10)]
    repeated = parse_algorithm("(R U)3' // inverse group\nR2'")
    assert repeated.moves == inverse_moves(('R', 'U') * 3) + ('R2',)
    assert normalized_state(parse_algorithm('x y z')) == _solved()
    assert final(alg.expanded + ' ' + ' '.join(inverse_moves(alg.moves))) == _solved()


@pytest.mark.parametrize('source', ['', '[R]', '[R,]', '[,U]', '(R U', 'R)', '[R:U',
                                    'R3', 'Mw', 'xxw', 'R + U', '(R U)9999',
                                    '(R)100000000000', '(' * 18 + 'R' + ')' * 18,
                                    'R ' * 601, 'R' * 8001])
def test_invalid_or_excessive_input_is_rejected(source):
    with pytest.raises(ValueError):
        parse_algorithm(source)
