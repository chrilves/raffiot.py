from unittest import TestCase

import hypothesis.strategies as st
from hypothesis import given

from raffiot.val import *
from raffiot.result import Ok
from raffiot import io


class TestVal(TestCase):
    def test_get(self):
        assert Val(5).get() == 5

    def test_get_io(self):
        return Val(5).get_io().run(None) == Ok(5)

    def get_rs(self):
        return Val(5).get_rs().use(io.pure).run(None) == Ok(5)

    def test_pure(self):
        assert Val.pure(5) == Val(5)

    def test_map(self):
        assert Val(5).map(lambda x: 10 * x) == Val(50)

    def test_flat_map(self):
        assert Val(5).flat_map(lambda x: Val(10 * x)) == Val(50)

    def test_zip(self):
        assert Val.zip(Val(5), Val("toto")) == Val([5, "toto"])

    def test_zip_with(self):
        assert Val(5).zip_with(Val("toto")) == Val([5, "toto"])

    def test_ap(self):
        assert Val(lambda x, y: f"x={x}, y={y}").ap(Val(5), Val("toto")) == Val(
            "x=5, y=toto"
        )


class TestVar(TestCase):
    def test_get(self):
        assert Var(5).get() == 5

    def test_get_io(self):
        return Var(5).get_io().run(None) == Ok(5)

    def get_rs(self):
        return Var(5).get_rs().use(io.pure).run(None) == Ok(5)

    def test_set(self):
        x = Var(5)
        x.set(7)
        assert x.get() == 7

    def test_set_io(self):
        x = Var(5)
        x.set_io(7).run(None)
        assert x.get() == 7

    def test_set_rs(self):
        x = Var(5)
        x.set_rs(7).use(io.pure).run(None)
        assert x.get() == 7

    def test_pure(self):
        assert Var.pure(5) == Var(5)

    def test_map(self):
        assert Var(5).map(lambda x: 10 * x) == Var(50)

    def test_flat_map(self):
        assert Var(5).flat_map(lambda x: Var(10 * x)) == Var(50)

    def test_zip(self):
        assert Var.zip(Var(5), Var("toto")) == Var([5, "toto"])

    def test_zip_with(self):
        assert Var(5).zip_with(Var("toto")) == Var([5, "toto"])

    def test_ap(self):
        assert Var(lambda x, y: f"x={x}, y={y}").ap(Var(5), Var("toto")) == Var(
            "x=5, y=toto"
        )


def test_sequence():
    assert sequence(5, 6, 7) == 7
