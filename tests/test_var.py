from unittest import TestCase

from raffiot import io, resource
from raffiot.result import Ok
from raffiot.var import *

x = 5
y = 6
z = 7


class TestVar(TestCase):
    def test_get(self) -> None:
        assert Var.create(x).flat_map(lambda var: var.get()).run(None) == Ok(x)

    def test_get_rs(self) -> None:
        assert Var.create_rs(x).flat_map(lambda var: var.get_rs()).use(io.pure).run(
            None
        ) == Ok(x)

    def test_set(self) -> None:
        assert Var.create(x).flat_map(
            lambda var: io.sequence(var.set(y), var.get())
        ).run(None) == Ok(y)

    def test_set_rs(self) -> None:
        assert Var.create(x).flat_map(
            lambda var: io.sequence(var.set_rs(y).use(io.pure), var.get())
        ).run(None) == Ok(y)

    def test_get_and_set(self) -> None:
        assert Var.create(x).flat_map(
            lambda var: io.zip(var.get_and_set(y), var.get())
        ).run(None) == Ok([x, y])

    def test_get_and_set_rs(self) -> None:
        assert Var.create(x).flat_map(
            lambda var: io.zip(var.get_and_set_rs(y).use(io.pure), var.get())
        ).run(None) == Ok([x, y])

    def test_update(self) -> None:
        assert Var.create(x).flat_map(lambda var: var.update(lambda i: (i + y, z))).run(
            None
        ) == Ok(UpdateResult(x, x + y, z))

    def test_update_io(self) -> None:
        assert Var.create(x).flat_map(
            lambda var: var.update_io(lambda i: io.pure((i + y, z)))
        ).run(None) == Ok(UpdateResult(x, x + y, z))

    def test_update_rs(self) -> None:
        assert Var.create(x).flat_map(
            lambda var: var.update_rs(lambda i: resource.pure((i + y, z))).use(io.pure)
        ).run(None) == Ok(UpdateResult(x, x + y, z))

    def test_traverse(self) -> None:
        assert Var.create(x).flat_map(
            lambda var1: var1.traverse(lambda i: io.pure(i + y)).flat_map(
                lambda var2: io.zip(var2.get_and_set(z), var1.get(), var2.get())
            )
        ).run(None) == Ok([x + y, x, z])

    def test_zip(self) -> None:
        assert io.zip(Var.create(x), Var.create(y)).flat_map(
            lambda vars: Var.zip(vars[0], vars[1])
        ).run(None) == Ok([x, y])

    def test_zip_with(self) -> None:
        assert io.zip(Var.create(x), Var.create(y)).flat_map(
            lambda vars: vars[0].zip_with(vars[1])
        ).run(None) == Ok([x, y])

    def test_zip_with(self) -> None:
        assert io.zip(
            Var.create(lambda i, j: i + j), Var.create(x), Var.create(y)
        ).flat_map(lambda vars: vars[0].ap(vars[1], vars[2])).run(None) == Ok(x + y)
