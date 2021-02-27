from concurrent.futures import Executor
from typing import List, Any, TypeVar
from unittest import TestCase

import hypothesis.strategies as st
from hypothesis import given

from raffiot import _MatchError
from raffiot import io
from raffiot.io import IO
from raffiot.resource import *
from raffiot.result import Result, Ok, Error, Panic

R = TypeVar("R", contravariant=True)
E = TypeVar("E", covariant=True)
A = TypeVar("A", covariant=True)


class TestResource(TestCase):
    @given(st.integers())
    def test_pure(self, i: int) -> None:
        assert pure(i).use(io.pure).run(None) == Ok(i)

    @given(st.integers())
    def test_flatten(self, i: int) -> None:
        assert pure(pure(i)).flatten().use(io.pure).run(None) == Ok(i)

    @given(st.text(), st.text())
    def test_ap(self, u: str, v: str) -> None:
        assert pure(lambda x, y: x + y).ap(pure(u), pure(v)).use(io.pure).run(
            None
        ).raise_on_panic() == Ok(u + v)

    @given(st.text())
    def test_error(self, err: str) -> None:
        assert error(err).use(io.pure).run(None) == Error(err)

    @given(st.text(), st.text())
    def test_map_error(self, u: str, v: str) -> None:
        assert error(u).map_error(lambda x: x + v).use(io.pure).run(None) == Error(
            u + v
        )

    @given(st.text(), st.text())
    def test_catch_error(self, u: str, v: str) -> None:
        assert error(u).catch(lambda x: pure(x + v)).use(io.pure).run(None) == Ok(u + v)

    @given(st.text(), st.text())
    def test_not_catch_ok(self, u: str, v: str) -> None:
        assert pure(u).catch(lambda x: pure(x + v)).use(io.pure).run(None) == Ok(u)

    @given(st.text(), st.text())
    def test_not_catch_panic(self, u: str, v: str) -> None:
        pan = _MatchError(u)
        assert panic(pan).catch(lambda x: pure(x + v)).use(io.pure).run(None) == Panic(
            pan
        )

    @given(st.text())
    def test_panic(self, err: str) -> None:
        pan = _MatchError(err)
        assert panic(pan).use(io.pure).run(None) == Panic(pan)

    @given(st.text(), st.text())
    def test_map_panic(self, u: str, v: str) -> None:
        pu = _MatchError(u)
        puv = _MatchError(u + v)
        assert panic(pu).map_panic(lambda x: _MatchError(x.message + v)).use(
            io.pure
        ).run(None) == Panic(puv)

    @given(st.text(), st.text())
    def test_recover_panic(self, u: str, v: str) -> None:
        pu = _MatchError(u)
        assert panic(pu).recover(lambda x: pure(x.message + v)).use(io.pure).run(
            None
        ) == Ok(u + v)

    @given(st.text(), st.text())
    def test_not_recover_ok(self, u: str, v: str) -> None:
        assert pure(u).recover(lambda x: pure(v)).use(io.pure).run(None) == Ok(u)

    @given(st.text(), st.text())
    def test_not_catch_error(self, u: str, v: str) -> None:
        assert error(u).catch(lambda x: pure(v)).use(io.pure).run(None) == Ok(v)

    @given(st.text())
    def test_panic(self, pan: str) -> None:
        assert panic(_MatchError(pan)).use(io.pure).run(None) == Panic(_MatchError(pan))

    @given(st.text(), st.text())
    def test_on_failure_ok(self, u: str, v: str) -> None:
        assert pure(u).on_failure(lambda x: pure(v)).use(io.pure).run(None) == Ok(u)

    @given(st.text(), st.text())
    def test_on_failure_error(self, u: str, v: str) -> None:
        assert error(u).map(lambda _: v).on_failure(pure).use(io.pure).run(None) == Ok(
            Error(u)
        )

    @given(st.text(), st.text())
    def test_on_failure_panic(self, u: str, v: str) -> None:
        pu = _MatchError(u)
        assert panic(pu).map(lambda _: v).on_failure(pure).use(io.pure).run(None) == Ok(
            Panic(pu)
        )

    @given(st.text())
    def test_read(self, i: st.integers()) -> None:
        assert read().use(io.pure).run(i) == Ok(i)

    @given(st.text(), st.text())
    def test_map_read(self, u: str, v: str) -> None:
        assert read().contra_map_read(lambda x: x + v).use(io.pure).run(u) == Ok(u + v)

    @given(st.text())
    def test_attempt_ok(self, u: str) -> None:
        assert pure(u).attempt().use(io.pure).run(None) == Ok(Ok(u))

    @given(st.text())
    def test_attempt_error(self, u: str) -> None:
        assert error(u).attempt().use(io.pure).run(None) == Ok(Error(u))

    @given(st.text())
    def test_attempt_panic(self, u: str) -> None:
        pu = _MatchError(u)
        assert panic(pu).attempt().use(io.pure).run(None) == Ok(Panic(pu))

    @given(st.text())
    def test_from_ok(self, u: str) -> None:
        x = Ok(u)
        assert from_result(x).use(io.pure).run(None) == x

    @given(st.text())
    def test_from_error(self, u: str) -> None:
        x = Error(u)
        assert from_result(x).use(io.pure).run(None) == x

    @given(st.text())
    def test_from_panic(self, u: str) -> None:
        x = Panic(_MatchError(u))
        assert from_result(x).use(io.pure).run(None) == x

    @given(st.integers(min_value=1000, max_value=2000))
    def test_defer(self, i: int) -> None:
        def f(j: int) -> IO[Any, Any, int]:
            if j <= 0:
                return pure(0)
            else:
                return defer_resource(f, j - 1).map(lambda x: x + 2)

        assert f(i).use(io.pure).run(None) == Ok(2 * i)

    @given(st.integers(), st.integers())
    def test_defer_read(self, i: int, k: int) -> None:
        def g(j: int) -> Result[E, A]:
            if j % 3 == 0:
                return Ok(j)
            if j % 3 == 1:
                return Error(j)
            return Panic(_MatchError(j))

        def f(context: R, executor: Executor, j: int) -> Result[E, A]:
            return g(j + k)

        assert defer_read(f, i).use(io.pure).run(k) == g(i + k)

    @given(st.integers(min_value=1000, max_value=2000))
    def test_defer_read_resource(self, i: int) -> None:
        def f(context: R, executor: Executor, j: int) -> Resource[Any, Any, int]:
            if j <= 0:
                return pure(0)
            else:
                return defer_read_resource(f, j - 1).map(lambda x: x + 2)

        assert defer_read_resource(f, i).use(io.pure).run(None) == Ok(2 * i)

    @given(st.integers(min_value=0, max_value=10))
    def test_recursion(self, i: int) -> None:
        def f(j: int) -> IO[Any, Any, int]:
            if j <= 0:
                return pure(0)
            else:
                return pure(j).flat_map(lambda x: f(j - 1).map(lambda y: x + y))

        assert f(i).use(io.pure).run(None) == Ok(i * (i + 1) / 2) if i >= 0 else 0

    @given(st.lists(st.integers()))
    def test_traverse(self, l: List[int]) -> None:
        var = []

        def f(x: int) -> Resource[None, None, int]:
            return defer(lambda: var.append(x)).then(pure(x * 2))

        assert traverse(l, f).use(io.pure).run(None) == Ok([x * 2 for x in l])
        assert var == l

    @given(st.lists(st.integers()))
    def test_yield(self, l: List[int]) -> None:
        def select_io(i: int):
            if i % 2 == 0:
                return yield_()
            return pure(i)

        assert zip([select_io(i) for i in l]).use(io.pure).run(None) == Ok(
            [(None if i % 2 == 0 else i) for i in l]
        )

    @given(st.text(), st.lists(st.text()))
    def test_async(self, s: str, l: List[str]) -> None:

        expected = s
        for u in l:
            expected += u

        def get_async(v, u):
            def f(r, executor, k):
                def h():
                    k(Ok(v + u))

                return executor.submit(h)

            return async_(f)

        ret = pure(s)
        for u in l:
            ret = (lambda ret, u: ret.flat_map(lambda v: get_async(v, u)))(ret, u)

        assert ret.use(io.pure).run(None).raise_on_panic() == Ok(expected)

    def test_executor(self) -> None:
        a = 10
        assert pure(a).flat_map(lambda r: read_executor().then(pure(r))).use(
            io.pure
        ).run(None) == Ok(a)

    def test_contra_map_executor_ok(self) -> None:
        a = 10
        assert pure(a).contra_map_executor(lambda e: e).use(io.pure).run(None) == Ok(a)

    def test_contra_map_executor_fail(self) -> None:
        a = 10
        assert (
            pure(a)
            .contra_map_executor(lambda e: 1 / 0)
            .use(io.pure)
            .run(None)
            .is_panic()
        )

    def test_contra_map_executor_type_error(self) -> None:
        a = 10
        assert (
            pure(a)
            .contra_map_executor(lambda e: "not an executor")
            .use(io.pure)
            .run(None)
            .is_panic()
        )

    @given(
        st.booleans(),
        st.booleans(),
        st.booleans(),
        st.booleans(),
        st.booleans(),
        st.booleans(),
    )
    def test_use_basic(
        self,
        can_open: bool,
        panic_open: bool,
        can_close: bool,
        panic_close: bool,
        can_use: bool,
        panic_use,
    ) -> None:
        i = 0
        opened = 0

        def incr():
            nonlocal opened
            opened += 1
            return i

        def decr():
            nonlocal opened
            opened -= 1

        open = (
            io.defer(incr)
            if can_open
            else (io.panic("panic open") if panic_open else io.error("error open"))
        )
        close = (
            io.defer(decr)
            if can_close
            else (io.panic("panic close") if panic_close else io.error("error close"))
        )

        def f_use(a):
            return (
                io.pure(a)
                if can_use
                else (io.panic("panic use") if panic_use else io.error("error use"))
            )

        rs = Resource(open.map(lambda a: (a, close)))
        ret = rs.use(f_use).run(None)
        assert opened == (1 if can_open and not can_close else 0)
        if can_open and can_use:
            assert ret == Ok(i)

    @given(
        st.booleans(),
        st.booleans(),
        st.booleans(),
        st.booleans(),
        st.booleans(),
        st.booleans(),
        st.booleans(),
    )
    def test_use_map(
        self,
        can_open: bool,
        panic_open: bool,
        can_close: bool,
        panic_close: bool,
        can_use: bool,
        panic_use: bool,
        can_map: bool,
    ) -> None:
        i = 10
        opened = 0

        def incr():
            nonlocal opened
            opened += 1
            return i

        def decr():
            nonlocal opened
            opened -= 1

        open = (
            io.defer(incr)
            if can_open
            else (io.panic("panic open") if panic_open else io.error("error open"))
        )
        close = (
            io.defer(decr)
            if can_close
            else (io.panic("panic close") if panic_close else io.error("error close"))
        )

        def f_use(a):
            return (
                io.pure(a)
                if can_use
                else (io.panic("panic use") if panic_use else io.error("error use"))
            )

        rs = Resource(open.map(lambda a: (a, close))).map(
            lambda x: (2 * x) if can_map else x / 0
        )
        ret = rs.use(f_use).run(None)
        assert opened == (1 if can_open and not can_close else 0)
        if can_open and can_map and can_use:
            assert ret == Ok(2 * i)

    @given(
        st.booleans(),
        st.booleans(),
        st.booleans(),
        st.booleans(),
        st.booleans(),
        st.booleans(),
    )
    def test_use_flat_map(
        self,
        can_open_a: bool,
        can_close_a: bool,
        can_flat_map: bool,
        can_open_b: bool,
        can_close_b: bool,
        can_use: bool,
    ) -> None:
        i = 10
        opened_b = 0
        called_b = 0

        def incr_b():
            nonlocal opened_b
            nonlocal called_b
            print("Open B")
            opened_b += 1
            called_b += 1
            return i

        def decr_b():
            nonlocal opened_b
            opened_b -= 1

        open_b = io.defer(incr_b) if can_open_b else io.panic("panic open b")
        close_b = io.defer(decr_b) if can_close_b else io.error("error close b")

        rs_b = Resource(open_b.map(lambda b: (b, close_b)))

        opened_a = 0
        called_a = 0

        def incr_a():
            nonlocal opened_a
            nonlocal called_a
            opened_a += 1
            called_a += 1
            return rs_b

        def decr_a():
            nonlocal opened_a
            opened_a -= 1

        open_a = io.defer(incr_a) if can_open_a else io.error("error open a")
        close_a = io.defer(decr_a) if can_close_a else io.panic("panic close_a")

        def f_use(x):
            return io.pure(x) if can_use else io.panic("panic use")

        rs_a = Resource(open_a.map(lambda a: (a, close_a)))

        rs = rs_a.flat_map(lambda r: r if can_flat_map else error("error flat map"))
        ret = rs.use(f_use).run(None)

        assert called_a == (1 if can_open_a else 0)
        assert opened_a == (1 if can_open_a and not can_close_a else 0)
        assert called_b == (1 if can_open_a and can_flat_map and can_open_b else 0)
        assert opened_b == (
            1 if can_open_a and can_flat_map and can_open_b and not can_close_b else 0
        )
        if can_open_a and can_flat_map and can_open_b and can_use:
            assert ret.raise_on_panic() == Ok(i)

    @given(
        st.booleans(),
        st.booleans(),
        st.booleans(),
        st.booleans(),
        st.booleans(),
    )
    def test_use_zip(
        self,
        can_open_a: bool,
        can_close_a: bool,
        can_open_b: bool,
        can_close_b: bool,
        can_use: bool,
    ) -> None:

        ret_a = "a"
        ret_b = "b"

        opened_a = 0
        called_a = 0

        def incr_a():
            nonlocal opened_a
            nonlocal called_a
            opened_a += 1
            called_a += 1
            return ret_a

        def decr_a():
            nonlocal opened_a
            opened_a -= 1

        open_a = io.defer(incr_a) if can_open_a else io.error("error open a")
        close_a = io.defer(decr_a) if can_close_a else io.panic("panic close_a")

        rs_a = Resource(open_a.map(lambda a: (a, close_a)))

        opened_b = 0
        called_b = 0

        def incr_b():
            nonlocal opened_b
            nonlocal called_b
            print("Open B")
            opened_b += 1
            called_b += 1
            return ret_b

        def decr_b():
            nonlocal opened_b
            opened_b -= 1

        open_b = io.defer(incr_b) if can_open_b else io.panic("panic open b")
        close_b = io.defer(decr_b) if can_close_b else io.error("error close b")

        rs_b = Resource(open_b.map(lambda b: (b, close_b)))

        def f_use(x):
            return io.pure(x) if can_use else io.panic("panic use")

        rs_a = Resource(open_a.map(lambda a: (a, close_a)))

        ret = zip(rs_a, rs_b).use(f_use).run(None)

        assert called_a == (1 if can_open_a else 0)
        assert called_b == (1 if can_open_b else 0)
        assert opened_a == (1 if can_open_a and not can_close_a else 0)
        assert opened_b == (1 if can_open_b and not can_close_b else 0)
        if can_open_a and can_open_b and can_use:
            assert ret.raise_on_panic() == Ok([ret_a, ret_b])
