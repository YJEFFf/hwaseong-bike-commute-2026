import pytest

from analysis.scenarios import jaccard_topn, topn_inclusion


def test_jaccard_topn():
    assert jaccard_topn([[1, 2, 3, 4], [1, 2, 5, 6]], n=4) == 2 / 6
    assert jaccard_topn([[1, 2], [1, 2], [2, 1]], n=2) == 1.0


def test_jaccard_topn_raises_on_fewer_than_two_rankings():
    with pytest.raises(ValueError):
        jaccard_topn([[1, 2, 3]], n=2)

    with pytest.raises(ValueError):
        jaccard_topn([], n=2)


def test_topn_inclusion():
    assert topn_inclusion([[1, 2], [1, 3]], n=2) == {1: 1.0, 2: 0.5, 3: 0.5}
