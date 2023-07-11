import pytest

from tja2fumen.utils import computeSoulGaugeBytes


@pytest.mark.skip("Incomplete test")
@pytest.mark.parametrize('difficulty,stars,n_notes,b20,b21', [
    ['Easy', 1, 24, 165, 254], ['Easy', 1, 54, 102, 255], ['Easy', 1, 112, 182, 255],
    # TODO: Fetch official fumen values for each difficulty-star pairing
    # ['Easy', 2, 0, 0, 0], ['Easy', 2, 0, 0, 0], ['Easy', 3, 0, 0, 0], ['Easy', 3, 0, 0, 0],
    # ['Easy', 4, 0, 0, 0], ['Easy', 4, 0, 0, 0], ['Easy', 5, 0, 0, 0], ['Easy', 5, 0, 0, 0],
    # ['Normal', 1, 0, 0, 0], ['Normal', 1, 0, 0, 0], ['Normal', 2, 0, 0, 0], ['Normal', 2, 0, 0, 0],
    # ['Normal', 3, 0, 0, 0], ['Normal', 3, 0, 0, 0], ['Normal', 3, 0, 0, 0],
    # ['Normal', 4, 0, 0, 0], ['Normal', 4, 0, 0, 0], ['Normal', 4, 0, 0, 0],
    # ['Normal', 5, 0, 0, 0], ['Normal', 6, 0, 0, 0], ['Normal', 7, 0, 0, 0],
    # ['Hard', 1, 0, 0, 0], ['Hard', 1, 0, 0, 0], ['Hard', 2, 0, 0, 0], ['Hard', 2, 0, 0, 0],
    # ['Hard', 3, 0, 0, 0], ['Hard', 3, 0, 0, 0], ['Hard', 3, 0, 0, 0],
    # ['Hard', 4, 0, 0, 0], ['Hard', 4, 0, 0, 0], ['Hard', 4, 0, 0, 0],
    # ['Hard', 5, 0, 0, 0], ['Hard', 6, 0, 0, 0], ['Hard', 7, 0, 0, 0], ['Hard', 8, 0, 0, 0],
    # ['Oni', 1, 0, 0, 0], ['Oni', 2, 0, 0, 0], ['Oni', 3, 0, 0, 0],
    # ['Oni', 4, 0, 0, 0], ['Oni', 5, 0, 0, 0], ['Oni', 6, 0, 0, 0], ['Oni', 7, 0, 0, 0],
    # ['Oni', 8, 0, 0, 0], ['Oni', 8, 0, 0, 0], ['Oni', 8, 0, 0, 0],
    # ['Oni', 9, 0, 0, 0], ['Oni', 9, 0, 0, 0], ['Oni', 10, 0, 0, 0], ['Oni', 10, 0, 0, 0],
])
def test_official_fumen_values(difficulty, stars, n_notes, b20, b21):
    assert computeSoulGaugeBytes(n_notes, difficulty, stars) == (b20, b21)
