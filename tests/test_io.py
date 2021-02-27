from typing import List, Any, TypeVar
from unittest import TestCase

import hypothesis.strategies as st
from hypothesis import given

from raffiot import _MatchError
from raffiot.io import *
from raffiot.result import Result, Ok, Error, Panic
from concurrent.futures import Executor

R = TypeVar("R", contravariant=True)
E = TypeVar("E", covariant=True)
A = TypeVar("A", covariant=True)


class TestIO(TestCase):
    @given(st.integers())
    def test_pure(self, i: int) -> None:
        assert pure(i).run(None) == Ok(i)

    @given(st.integers())
    def test_flatten(self, i: int) -> None:
        assert pure(pure(i)).flatten().run(None) == Ok(i)

    @given(st.text(), st.text())
    def test_ap(self, u: str, v: str) -> None:
        assert pure(lambda x, y: x + y).ap(pure(u), pure(v)).run(None) == Ok(u + v)

    @given(st.text(), st.text())
    def test_ap_error(self, u: str, v: str) -> None:
        assert pure(lambda x, y: x + y).ap(error(u), pure(v)).run(None) == Error(u)

    @given(st.text(), st.text())
    def test_ap_panic(self, u: str, v: str) -> None:
        assert pure(lambda x, y: x + y).ap(pure(u), panic(_MatchError(v))).run(
            None
        ) == Panic(_MatchError(v))

    @given(st.lists(st.text()))
    def test_zip(self, l: List[str]) -> None:
        assert zip([pure(s) for s in l]).run(None) == Ok(l)

    @given(st.text(), st.text())
    def test_zip_error(self, u: str, v: str) -> None:
        assert zip(error(u), pure(v)).run(None) == Error(u)

    @given(st.text(), st.text())
    def test_zip_panic(self, u: str, v: str) -> None:
        assert zip(pure(u), panic(_MatchError(v))).run(None) == Panic(_MatchError(v))

    @given(st.integers(), st.integers(), st.integers(), st.lists(st.text()))
    def test_sequence(self, x: int, y: int, z: int, l: List[str]) -> None:
        expected = [x, y, z]
        state = [None, None, None]

        def f(i):
            state[i] = expected[i]

        assert sequence(
            [defer(f, 0), defer(f, 1), defer(f, 2)] + [pure(s) for s in l]
        ).run(None) == Ok(None if not l else l[-1])
        assert state == expected

    @given(st.text(), st.text(), st.text())
    def test_sequence_error(self, u: str, v: str, w: str) -> None:
        arr = [u, v]
        state = [None, None]

        def f(i):
            state[i] = arr[i]

        assert sequence(defer(f, 0), error(w), defer(f, 1)).run(None) == Error(w)
        assert state == [u, None]

    @given(st.text(), st.text(), st.text())
    def test_sequence_panic(self, u: str, v: str, w: str) -> None:
        arr = [u, v]
        state = [None, None]

        def f(i):
            state[i] = arr[i]

        assert sequence(defer(f, 0), panic(_MatchError(w)), defer(f, 1)).run(
            None
        ) == Panic(_MatchError(w))
        assert state == [u, None]

    @given(st.text())
    def test_error(self, err: str) -> None:
        assert error(err).run(None) == Error(err)

    @given(st.text(), st.text())
    def test_map_error(self, u: str, v: str) -> None:
        assert error(u).map_error(lambda x: x + v).run(None) == Error(u + v)

    @given(st.text(), st.text())
    def test_catch_error(self, u: str, v: str) -> None:
        assert error(u).catch(lambda x: pure(x + v)).run(None) == Ok(u + v)

    @given(st.text(), st.text())
    def test_not_catch_ok(self, u: str, v: str) -> None:
        assert pure(u).catch(lambda x: pure(x + v)).run(None) == Ok(u)

    @given(st.text(), st.text())
    def test_not_catch_panic(self, u: str, v: str) -> None:
        pan = _MatchError(u)
        assert panic(pan).catch(lambda x: pure(x + v)).run(None) == Panic(pan)

    @given(st.text())
    def test_panic(self, err: str) -> None:
        pan = _MatchError(err)
        assert panic(pan).run(None) == Panic(pan)

    @given(st.text(), st.text())
    def test_map_panic(self, u: str, v: str) -> None:
        pu = _MatchError(u)
        puv = _MatchError(u + v)
        assert panic(pu).map_panic(lambda x: _MatchError(x.message + v)).run(
            None
        ) == Panic(puv)

    @given(st.text(), st.text())
    def test_recover_panic(self, u: str, v: str) -> None:
        pu = _MatchError(u)
        assert panic(pu).recover(lambda x: pure(x.message + v)).run(None) == Ok(u + v)

    @given(st.text(), st.text())
    def test_not_recover_ok(self, u: str, v: str) -> None:
        assert pure(u).recover(lambda x: pure(v)).run(None) == Ok(u)

    @given(st.text(), st.text())
    def test_not_catch_error(self, u: str, v: str) -> None:
        assert error(u).catch(lambda x: pure(v)).run(None) == Ok(v)

    @given(st.text())
    def test_panic(self, pan: str) -> None:
        assert panic(_MatchError(pan)).run(None) == Panic(_MatchError(pan))

    @given(st.text(), st.text())
    def test_on_failure_ok(self, u: str, v: str) -> None:
        assert pure(u).on_failure(lambda x: pure(v)).run(None) == Ok(u)

    @given(st.text(), st.text())
    def test_on_failure_error(self, u: str, v: str) -> None:
        assert error(u).map(lambda _: v).on_failure(pure).run(None) == Ok(Error(u))

    @given(st.text(), st.text())
    def test_on_failure_panic(self, u: str, v: str) -> None:
        pu = _MatchError(u)
        assert panic(pu).map(lambda _: v).on_failure(pure).run(None) == Ok(Panic(pu))

    @given(st.text())
    def test_read(self, i: st.integers()) -> None:
        assert read().run(i) == Ok(i)

    @given(st.text(), st.text())
    def test_map_read(self, u: str, v: str) -> None:
        assert read().contra_map_read(lambda x: x + v).run(u) == Ok(u + v)

    @given(st.text())
    def test_attempt_ok(self, u: str) -> None:
        assert pure(u).attempt().run(None) == Ok(Ok(u))

    @given(st.text())
    def test_attempt_error(self, u: str) -> None:
        assert error(u).attempt().run(None).raise_on_panic() == Ok(Error(u))

    @given(st.text())
    def test_attempt_panic(self, u: str) -> None:
        pu = _MatchError(u)
        assert panic(pu).attempt().run(None) == Ok(Panic(pu))

    @given(st.text())
    def test_from_ok(self, u: str) -> None:
        x = Ok(u)
        assert from_result(x).run(None) == x

    @given(st.text())
    def test_from_error(self, u: str) -> None:
        x = Error(u)
        assert from_result(x).run(None) == x

    @given(st.text())
    def test_from_panic(self, u: str) -> None:
        x = Panic(_MatchError(u))
        assert from_result(x).run(None) == x

    @given(st.integers(min_value=1000, max_value=2000))
    def test_defer(self, i: int) -> None:
        def f(j: int) -> IO[Any, Any, int]:
            if j <= 0:
                return pure(0)
            else:
                return defer_io(f, j - 1).map(lambda x: x + 2)

        assert f(i).run(None) == Ok(2 * i)

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

        assert defer_read(f, i).run(k) == g(i + k)

    @given(st.integers(min_value=1000, max_value=2000))
    def test_defer_read_io(self, i: int) -> None:
        def f(context: R, executor: Executor, j: int) -> IO[Any, Any, int]:
            if j <= 0:
                return pure(0)
            else:
                return defer_read_io(f, j - 1).map(lambda x: x + 2)

        assert defer_read_io(f, i).run(None) == Ok(2 * i)

    @given(st.integers(min_value=0, max_value=10))
    def test_recursion(self, i: int) -> None:
        def f(j: int) -> IO[Any, Any, int]:
            if j <= 0:
                return pure(0)
            else:
                return pure(j).flat_map(lambda x: f(j - 1).map(lambda y: x + y))

        assert f(i).run(None) == Ok(i * (i + 1) / 2) if i >= 0 else 0

    @given(st.lists(st.integers()))
    def test_traverse(self, l: List[int]) -> None:
        var = []

        def f(x: int) -> IO[None, None, int]:
            return defer(lambda: var.append(x)).then(pure(x * 2))

        assert traverse(l, f).run(None).map(list) == Ok([x * 2 for x in l])
        assert var == l

    @given(st.lists(st.integers()), st.integers())
    def test_yield(self, l: List[int], x: int) -> None:
        def select_io(i: int):
            if i % 2 == 0:
                return yield_()
            return pure(i)

        ios = [select_io(i) for i in l] + [pure(x)]

        assert sequence(ios).run(None).raise_on_panic() == Ok(x)

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

        assert ret.run(None).raise_on_panic() == Ok(expected)

    def test_executor(self) -> None:
        a = 10
        assert pure(a).flat_map(lambda r: read_executor().then(pure(r))).run(
            None
        ) == Ok(a)

    def test_contra_map_executor_ok(self) -> None:
        a = 10
        assert pure(a).contra_map_executor(lambda e: e).run(None) == Ok(a)

    def test_contra_map_executor_fail(self) -> None:
        a = 10
        assert pure(a).contra_map_executor(lambda e: 1 / 0).run(None).is_panic()

    def test_contra_map_executor_type_error(self) -> None:
        a = 10
        assert (
            pure(a)
            .contra_map_executor(lambda e: "not an executor")
            .run(None)
            .is_panic()
        )

    @given(st.lists(st.integers()))
    def test_parallel(self, l: List[str]) -> None:
        def f(j: int) -> IO[R, E, A]:
            if j % 5 == 0:
                return pure(j)
            if j % 5 == 1:
                return error(j)
            if j % 5 == 2:
                return panic(_MatchError(j))
            if j % 5 == 3:
                return defer(print, j)

            def h():
                raise _MatchError(j)

            return defer(h)

        def g(j: int) -> Result[E, A]:
            if j % 5 == 0:
                return Ok(j)
            if j % 5 == 1:
                return Error(j)
            if j % 5 == 2:
                return Panic(_MatchError(j))
            if j % 5 == 3:
                return Ok(None)
            return Panic(_MatchError(j))

        assert parallel([f(s) for s in l]).flat_map(wait).run(None) == Ok(
            [g(s) for s in l]
        )

    def test_then_keep(self):
        assert pure(5).then_keep(pure(7)).run(None) == Ok(5)
