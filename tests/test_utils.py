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
