from unittest import TestCase

from raffiot.utils import *

x = 5
y = 6
z = 7


def test_sequence():
    assert seq(x, y, z) == z


class TestMultipleExceptions(TestCase):
    def test_merge_none(self):
        assert MultipleExceptions.merge() == MultipleExceptions([], [])

    def test_merge_one(self):
        exn = MatchError(x)
        assert MultipleExceptions.merge(exn) == exn

    def test_merge_list_one(self):
        exn = MatchError(x)
        assert MultipleExceptions.merge([exn]) == exn

    def test_merge_list_one(self):
        exn_x = MatchError(x)
        exn_y = MatchError(y)
        exn_z = MatchError(z)
        assert MultipleExceptions.merge(
            MultipleExceptions([exn_x], []), exn_y, MultipleExceptions([exn_z], [])
        ) == MultipleExceptions([exn_x, exn_y, exn_z], [])


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
