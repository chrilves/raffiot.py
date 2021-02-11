from hypothesis import given
import hypothesis.strategies as st
from unittest import TestCase
from raffiot.result import *


class TestResult(TestCase):
    @given(st.text(), st.text())
    def test_flat_map(self, i: int, j: int) -> None:
        assert pure(i).flat_map(lambda x: pure(x + j)) == pure(i + j)

    @given(st.text(), st.text())
    def test_ap(self, i: int, j: int) -> None:
        assert pure(lambda x: x + j).ap(pure(i)) == pure(i + j)

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
