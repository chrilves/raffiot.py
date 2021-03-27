from typing import List
from unittest import TestCase

import hypothesis.strategies as st
from hypothesis import given

from raffiot.result import *
from raffiot.utils import MatchError, ComputationStatus, MultipleExceptions


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
        assert pure(1).map(lambda x: x / 0).recover(lambda x, y: pure(i)) == pure(i)

    @given(st.lists(st.integers()))
    def test_traverse(self, l: List[int]) -> None:
        var = []

        def f(x: int) -> Result[None, int]:
            var.append(x)
            return pure(x * 2)

        assert traverse(l, f) == Ok([x * 2 for x in l])
        assert var == l

    @given(st.lists(st.integers()))
    def test_zip(self, l: List[int]) -> None:
        def int_to_result(i: int) -> Result[int, int]:
            if i % 3 == 0:
                return pure(i)
            if i % 3 == 1:
                return error(i)
            return panic(MatchError(f"{i}"))

        results = [int_to_result(i) for i in l]

        oks = [i for i in l if i % 3 == 0]
        errs = [i for i in l if i % 3 == 1]
        panics = [MatchError(f"{i}") for i in l if i % 3 == 2]

        assert zip(results) == (
            Panic(exceptions=panics, errors=errs)
            if panics
            else (Errors(errs) if errs else Ok(oks))
        )

    @given(st.lists(st.integers()))
    def test_sequence(self, l: List[int]) -> None:
        def int_to_result(i: int) -> Result[int, int]:
            if i % 3 == 0:
                return ok(i)
            if i % 3 == 1:
                return error(i)
            return panic(MatchError(f"{i}"))

        results = [int_to_result(i) for i in l]

        oks = l[-1] if l and l[-1] % 3 == 0 else None
        errs = [i for i in l if i % 3 == 1]
        panics = [MatchError(f"{i}") for i in l if i % 3 == 2]

        assert sequence(results) == (
            Panic(exceptions=panics, errors=errs)
            if panics
            else (Errors(errs) if errs else Ok(oks))
        )

    def test_computation_status_ok(self) -> None:
        assert pure(()).to_computation_status() == ComputationStatus.SUCCEEDED

    def test_computation_status_error(self) -> None:
        assert error(()).to_computation_status() == ComputationStatus.FAILED

    def test_computation_status_panic(self) -> None:
        assert panic(MatchError("")).to_computation_status() == ComputationStatus.FAILED
