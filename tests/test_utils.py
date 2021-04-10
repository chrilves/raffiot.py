from unittest import TestCase

import hypothesis.strategies as st
from hypothesis import given

from raffiot.utils import *
from typing import List


def test_sequence():
    x = 5
    y = 6
    z = 7

    assert seq(x, y, z) == z


class TestTracedException(TestCase):
    def test_in_except_clause_itempotence(self):
        exn = TracedException(MatchError(""), "")
        assert isinstance(TracedException.in_except_clause(exn).exception, MatchError)

    def test_in_with_stack_trace_itempotence(self):
        exn = TracedException(MatchError(""), "")
        assert isinstance(TracedException.with_stack_trace(exn).exception, MatchError)

    def test_in_with_ensure_traced_itempotence(self):
        exn = TracedException(MatchError(""), "")
        assert isinstance(TracedException.ensure_traced(exn).exception, MatchError)


class TestMultipleExceptions(TestCase):
    @given(st.lists(st.lists(st.text())))
    def test_exns(self, l: List[str]):
        exceptions = [TracedException(MatchError(x), "") for x in l]
        assert MultipleExceptions.merge(*exceptions) == MultipleExceptions(
            exceptions=exceptions, errors=[]
        )

    @given(st.lists(st.lists(st.text())))
    def test_list_of_lists(self, l: List[List[str]]):
        list_exceptions = [[TracedException(MatchError(x), "") for x in y] for y in l]
        expected = [exn for y in list_exceptions for exn in y]
        assert MultipleExceptions.merge(*list_exceptions) == MultipleExceptions(
            exceptions=expected, errors=[]
        )

    @given(st.lists(st.lists(st.text())))
    def test_list_of_multiple(self, l: List[List[str]]):
        list_multiple = [
            MultipleExceptions.merge(*[TracedException(MatchError(x), "") for x in y])
            for y in l
        ]
        expected = [TracedException(MatchError(x), "") for y in l for x in y]
        assert MultipleExceptions.merge(*list_multiple) == MultipleExceptions(
            exceptions=expected, errors=[]
        )
