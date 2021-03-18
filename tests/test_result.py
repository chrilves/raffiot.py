from typing import List
from unittest import TestCase

import hypothesis.strategies as st
from hypothesis import given

from raffiot.result import *
from raffiot.utils import MatchError


class TestResult(TestCase):
    @given(st.text(), st.text())
    def test_flat_map(self, i: int, j: int) -> None:
        assert pure(i).flat_map(lambda x: pure(x + j)) == pure(i + j)

    @given(st.text(), st.text(), st.text())
    def test_ap(self, i: str, j: str, k: str) -> None:
        assert pure(lambda x, y: x + j + y).ap(pure(i), pure(k)) == pure(i + j + k)

    @given(st.text())
    def test_panic(self, i: int) -> None:
        assert pure(i).map(lambda x: x / 0).is_panic()

    @given(st.text())
    def test_recover(self, i: int) -> None:
        assert pure(1).map(lambda x: x / 0).recover(lambda x: pure(i)) == pure(i)

    @given(st.lists(st.integers()))
    def test_traverse(self, l: List[int]) -> None:
        var = []

        def f(x: int) -> Result[None, int]:
            var.append(x)
            return pure(x * 2)

        assert traverse(l, f) == Ok([x * 2 for x in l])
        assert var == l

    @given(st.text(), st.text())
    def test_zip_ok(self, i: str, j: str) -> None:
        assert zip(pure(i), pure(j)) == pure([i, j])

    @given(st.text(), st.text())
    def test_zip_error(self, i: str, j: str) -> None:
        assert zip(pure(i), error(j)) == error(j)

    @given(st.text(), st.text())
    def test_zip_panic(self, i: str, j: str) -> None:
        assert zip(error(i), panic(MatchError(j))) == panic(MatchError(j))
