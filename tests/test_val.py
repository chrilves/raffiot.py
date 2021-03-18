from unittest import TestCase

from raffiot import io
from raffiot.result import Ok
from raffiot.val import *

x = 5
y = 6
z = 7


class TestVal(TestCase):
    def test_get(self):
        assert Val(x).get() == x

    def test_get_io(self):
        return Val(x).get_io().run(None) == Ok(x)

    def get_rs(self):
        return Val(x).get_rs().use(io.pure).run(None) == Ok(x)

    def test_pure(self):
        assert Val.pure(x) == Val(x)

    def test_map(self):
        assert Val(x).map(lambda i: y * i) == Val(y * x)

    def test_traverse(self):
        assert Val(x).traverse(lambda i: io.pure(y * i)).run(None) == Ok(Val(y * x))

    def test_flat_map(self):
        assert Val(x).flat_map(lambda i: Val(y * i)) == Val(y * x)

    def test_flatten(self):
        assert Val(Val(x)).flatten() == Val(x)

    def test_zip(self):
        assert Val.zip(Val(x), Val(y)) == Val([x, y])

    def test_zip_with(self):
        assert Val(x).zip_with(Val(y)) == Val([x, y])

    def test_ap(self):
        assert Val(lambda i, j: f"x={i}, y={j}").ap(Val(x), Val(y)) == Val(
            f"x={x}, y={y}"
        )
