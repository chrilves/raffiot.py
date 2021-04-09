import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Any, TypeVar
from unittest import TestCase

import hypothesis.strategies as st
from hypothesis import given

from raffiot import result
from raffiot.io import *
from raffiot.result import Result
from raffiot.utils import MatchError, TracedException

R = TypeVar("R", contravariant=True)
E = TypeVar("E", covariant=True)
A = TypeVar("A", covariant=True)


class TestIO(TestCase):
    @given(st.integers())
    def test_pure(self, i: int) -> None:
        assert pure(i).run(None) == result.ok(i)

    @given(st.integers())
    def test_flatten(self, i: int) -> None:
        assert pure(pure(i)).flatten().run(None) == result.ok(i)

    @given(st.text(), st.text())
    def test_ap(self, u: str, v: str) -> None:
        assert pure(lambda x, y: x + y).ap(pure(u), pure(v)).run(None) == result.ok(
            u + v
        )

    @given(st.text(), st.text())
    def test_ap_error(self, u: str, v: str) -> None:
        assert pure(lambda x, y: x + y).ap(errors(u), pure(v)).run(
            None
        ) == result.errors(u)

    @given(st.text(), st.text())
    def test_ap_panic(self, u: str, v: str) -> None:
        exn = TracedException.with_stack_trace(MatchError(v))
        assert pure(lambda x, y: x + y).ap(pure(u), panic(exn)).run(
            None
        ) == result.panic(exn)

    @given(st.lists(st.text()))
    def test_zip(self, l: List[str]) -> None:
        assert zip([pure(s) for s in l]).run(None) == result.ok(l)

    @given(st.text(), st.text())
    def test_zip_error(self, u: str, v: str) -> None:
        assert zip(errors(u), pure(v)).run(None) == result.errors(u)

    @given(st.text(), st.text())
    def test_zip_panic(self, u: str, v: str) -> None:
        assert zip(pure(u), panic(TracedException(MatchError(v), ""))).run(
            None
        ) == result.panic(TracedException(MatchError(v), ""))

    @given(st.integers(), st.integers(), st.integers(), st.lists(st.text()))
    def test_sequence(self, x: int, y: int, z: int, l: List[str]) -> None:
        expected = [x, y, z]
        state = [None, None, None]

        def f(i):
            state[i] = expected[i]

        assert sequence(
            [defer(f, 0), defer(f, 1), defer(f, 2)] + [pure(s) for s in l]
        ).run(None) == result.ok(None if not l else l[-1])
        assert state == expected

    @given(st.text(), st.text(), st.text())
    def test_sequence_error(self, u: str, v: str, w: str) -> None:
        arr = [u, v]
        state = [None, None]

        def f(i):
            state[i] = arr[i]

        assert sequence(defer(f, 0), errors(w), defer(f, 1)).run(None) == result.error(
            w
        )
        assert state == [u, None]

    @given(st.text(), st.text(), st.text())
    def test_sequence_panic(self, u: str, v: str, w: str) -> None:
        arr = [u, v]
        state = [None, None]

        def f(i):
            state[i] = arr[i]

        assert sequence(
            defer(f, 0), panic(TracedException(MatchError(w), "")), defer(f, 1)
        ).run(None) == result.panic(TracedException(MatchError(w), ""))
        assert state == [u, None]

    @given(st.text())
    def test_error(self, err: str) -> None:
        assert errors(err).run(None) == result.error(err)

    @given(st.text(), st.text())
    def test_map_error(self, u: str, v: str) -> None:
        assert errors(u).map_error(lambda x: x + v).run(None) == result.error(u + v)

    @given(st.text(), st.text())
    def test_catch_error(self, u: str, v: str) -> None:
        assert errors(u).catch(lambda x: pure(x[0] + v)).run(None) == result.ok(u + v)

    @given(st.text(), st.text())
    def test_not_catch_ok(self, u: str, v: str) -> None:
        assert pure(u).catch(lambda x: pure(x + v)).run(None) == result.ok(u)

    @given(st.text(), st.text())
    def test_not_catch_panic(self, u: str, v: str) -> None:
        pan = TracedException.with_stack_trace(MatchError(u))
        assert panic(pan).catch(lambda x: pure(x + v)).run(None) == result.panic(pan)

    @given(st.text())
    def test_panic(self, err: str) -> None:
        pan = TracedException(MatchError(err), "")
        assert panic(pan).run(None) == result.panic(pan)

    @given(st.text(), st.text())
    def test_map_panic(self, u: str, v: str) -> None:
        pu = TracedException(MatchError(u), "")
        puv = TracedException(MatchError(u + v), "")
        assert panic(pu).map_panic(
            lambda x: TracedException(MatchError(x.exception.message + v), "")
        ).run(None) == result.panic(puv)

    @given(st.text(), st.text())
    def test_recover_panic(self, u: str, v: str) -> None:
        pu = TracedException(MatchError(u), "")
        assert panic(pu).recover(lambda x, e: pure(x[0].exception.message + v)).run(
            None
        ) == result.ok(u + v)

    @given(st.text(), st.text())
    def test_not_recover_ok(self, u: str, v: str) -> None:
        assert pure(u).recover(lambda x: pure(v)).run(None) == result.ok(u)

    @given(st.text(), st.text())
    def test_not_catch_error(self, u: str, v: str) -> None:
        assert error(u).catch(lambda x: pure(v)).run(None) == result.ok(v)

    @given(st.text(), st.text())
    def test_on_failure_ok(self, u: str, v: str) -> None:
        assert pure(u).on_failure(lambda x: pure(v)).run(None) == result.ok(u)

    @given(st.text(), st.text())
    def test_on_failure_error(self, u: str, v: str) -> None:
        assert errors(u).map(lambda _: v).on_failure(pure).run(None) == result.ok(
            result.error(u)
        )

    @given(st.text(), st.text())
    def test_on_failure_panic(self, u: str, v: str) -> None:
        pu = TracedException.with_stack_trace(MatchError(u))
        assert panic(pu).map(lambda _: v).on_failure(pure).run(None) == result.ok(
            result.panic(pu)
        )

    @given(st.text())
    def test_read(self, i: st.integers()) -> None:
        assert read.run(i) == result.ok(i)

    @given(st.text(), st.text())
    def test_map_read(self, u: str, v: str) -> None:
        assert read.contra_map_read(lambda x: x + v).run(u) == result.ok(u + v)

    @given(st.text())
    def test_attempt_ok(self, u: str) -> None:
        assert pure(u).attempt().run(None) == result.ok(result.ok(u))

    @given(st.text())
    def test_attempt_error(self, u: str) -> None:
        assert errors(u).attempt().run(None) == result.ok(result.error(u))

    @given(st.text())
    def test_attempt_panic(self, u: str) -> None:
        pu = TracedException.with_stack_trace(MatchError(u))
        assert panic(pu).attempt().run(None) == result.ok(result.panic(pu))

    @given(st.text())
    def test_from_ok(self, u: str) -> None:
        x = result.ok(u)
        assert from_result(x).run(None) == x

    @given(st.text())
    def test_from_error(self, u: str) -> None:
        x = result.error(u)
        assert from_result(x).run(None) == x

    @given(st.text())
    def test_from_panic(self, u: str) -> None:
        x = result.panic(MatchError(u))
        assert from_result(x).run(None) == x

    @given(st.integers(min_value=1000, max_value=2000))
    def test_defer(self, i: int) -> None:
        def f(j: int) -> IO[Any, Any, int]:
            if j <= 0:
                return pure(0)
            else:
                return defer_io(f, j - 1).map(lambda x: x + 2)

        assert f(i).run(None) == result.ok(2 * i)

    @given(st.integers(), st.integers())
    def test_defer_read(self, i: int, k: int) -> None:
        def g(j: int) -> Result[E, A]:
            if j % 3 == 0:
                return result.ok(j)
            if j % 3 == 1:
                return result.error(j)
            return result.panic(TracedException(MatchError(j), ""))

        def f(context: R, j: int) -> Result[E, A]:
            return g(j + k)

        assert defer_read(f, i).run(k) == g(i + k)

    @given(st.integers(min_value=1000, max_value=2000))
    def test_defer_read_io(self, i: int) -> None:
        def f(context: R, j: int) -> IO[Any, Any, int]:
            if j <= 0:
                return pure(0)
            else:
                return defer_read_io(f, j - 1).map(lambda x: x + 2)

        assert defer_read_io(f, i).run(None) == result.ok(2 * i)

    @given(st.integers(min_value=0, max_value=10))
    def test_recursion(self, i: int) -> None:
        def f(j: int) -> IO[Any, Any, int]:
            if j <= 0:
                return pure(0)
            else:
                return pure(j).flat_map(lambda x: f(j - 1).map(lambda y: x + y))

        assert f(i).run(None) == result.ok(i * (i + 1) / 2) if i >= 0 else 0

    @given(st.lists(st.integers()))
    def test_traverse(self, l: List[int]) -> None:
        var = []

        def f(x: int) -> IO[None, None, int]:
            return defer(lambda: var.append(x)).then(pure(x * 2))

        assert traverse(l, f).run(None).map(list) == result.ok([x * 2 for x in l])
        assert var == l

    @given(st.lists(st.integers()), st.integers())
    def test_yield(self, l: List[int], x: int) -> None:
        def select_io(i: int):
            if i % 2 == 0:
                return yield_
            return pure(i)

        ios = [select_io(i) for i in l] + [pure(x)]

        assert sequence(ios).run(None) == result.ok(x)

    @given(
        st.text(),
        st.lists(st.text(), min_size=0, max_size=3),
        st.floats(min_value=0, max_value=0.01),
    )
    def test_async(self, s: str, l: List[str], sleeping_time: float) -> None:
        with ThreadPoolExecutor() as pool:
            expected = s
            for u in l:
                expected += u

            def get_async(v, u):
                def f(r, k):
                    def h():
                        time.sleep(sleeping_time)
                        k(result.ok(v + u))

                    pool.submit(h)

                return async_(f)

            ret = pure(s)
            for u in l:
                ret = (lambda ret, u: ret.flat_map(lambda v: get_async(v, u)))(ret, u)

            assert ret.run(None) == result.ok(expected)

    @given(st.lists(st.integers()))
    def test_parallel(self, l: List[str]) -> None:
        def f(j: int) -> IO[R, E, A]:
            if j % 5 == 0:
                return pure(j)
            if j % 5 == 1:
                return error(j)
            if j % 5 == 2:
                return panic(TracedException(MatchError(j), ""))
            if j % 5 == 3:
                return defer(print, j)

            def h():
                raise TracedException(MatchError(j), "")

            return defer(h)

        def g(j: int) -> Result[E, A]:
            if j % 5 == 0:
                return result.ok(j)
            if j % 5 == 1:
                return result.error(j)
            if j % 5 == 2:
                return result.panic(TracedException(MatchError(j), ""))
            if j % 5 == 3:
                return result.ok(None)
            return result.panic(TracedException(MatchError(j), ""))

        assert parallel([f(s) for s in l]).flat_map(wait).run(None) == result.ok(
            [g(s) for s in l]
        )

    @given(st.lists(st.integers()))
    def test_parallel_wait_zip_ok(self, l: List[int]):
        assert zip_par([pure(i) for i in l]).run(None) == result.ok(l)

    def test_then_keep(self):
        assert pure(5).then_keep(pure(7)).run(None) == result.ok(5)

    def test_sleep(self):
        sleep_time = 2
        assert (
            defer(time.time)
            .flat_map(
                lambda beg: sleep(sleep_time)
                .then(defer(time.time))
                .map(lambda end: end - beg)
            )
            .run(None)
            .success
            >= sleep_time
        )
