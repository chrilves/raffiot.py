from hypothesis import given
import hypothesis.strategies as st
from unittest import TestCase
from raffiot.io import *
from raffiot import _MatchError


class TestResource(TestCase):
    @given(st.integers())
    def test_pure(self, i: int) -> None:
        assert pure(i).run(None) == result.Ok(i)

    @given(st.integers())
    def test_flatten(self, i: int) -> None:
        assert pure(pure(i)).flatten().run(None) == result.Ok(i)

    @given(st.text(), st.text())
    def test_ap(self, u: str, v: str) -> None:
        assert pure(lambda x, y: x + y).ap(pure(u), pure(v)).run(None) == result.Ok(
            u + v
        )

    @given(st.text(), st.text())
    def test_ap_error(self, u: str, v: str) -> None:
        assert pure(lambda x, y: x + y).ap(error(u), pure(v)).run(None) == result.Error(
            u
        )

    @given(st.text(), st.text())
    def test_ap_panic(self, u: str, v: str) -> None:
        assert pure(lambda x, y: x + y).ap(pure(u), panic(_MatchError(v))).run(
            None
        ) == result.Panic(_MatchError(v))

    @given(st.lists(st.text()))
    def test_zip(self, l: List[str]) -> None:
        assert zip([pure(s) for s in l]).run(None) == result.Ok(l)

    @given(st.text(), st.text())
    def test_zip_error(self, u: str, v: str) -> None:
        assert zip(error(u), pure(v)).run(None) == result.Error(u)

    @given(st.text(), st.text())
    def test_zip_panic(self, u: str, v: str) -> None:
        assert zip(pure(u), panic(_MatchError(v))).run(None) == result.Panic(
            _MatchError(v)
        )

    @given(st.text())
    def test_error(self, err: str) -> None:
        assert error(err).run(None) == result.Error(err)

    @given(st.text(), st.text())
    def test_map_error(self, u: str, v: str) -> None:
        assert error(u).map_error(lambda x: x + v).run(None) == result.Error(u + v)

    @given(st.text(), st.text())
    def test_catch_error(self, u: str, v: str) -> None:
        assert error(u).catch(lambda x: pure(x + v)).run(None) == result.Ok(u + v)

    @given(st.text(), st.text())
    def test_not_catch_ok(self, u: str, v: str) -> None:
        assert pure(u).catch(lambda x: pure(x + v)).run(None) == result.Ok(u)

    @given(st.text(), st.text())
    def test_not_catch_panic(self, u: str, v: str) -> None:
        pan = _MatchError(u)
        assert panic(pan).catch(lambda x: pure(x + v)).run(None) == result.Panic(pan)

    @given(st.text())
    def test_panic(self, err: str) -> None:
        pan = _MatchError(err)
        assert panic(pan).run(None) == result.Panic(pan)

    @given(st.text(), st.text())
    def test_map_panic(self, u: str, v: str) -> None:
        pu = _MatchError(u)
        puv = _MatchError(u + v)
        assert panic(pu).map_panic(lambda x: _MatchError(x.message + v)).run(
            None
        ) == result.Panic(puv)

    @given(st.text(), st.text())
    def test_recover_panic(self, u: str, v: str) -> None:
        pu = _MatchError(u)
        assert panic(pu).recover(lambda x: pure(x.message + v)).run(None) == result.Ok(
            u + v
        )

    @given(st.text(), st.text())
    def test_not_recover_ok(self, u: str, v: str) -> None:
        assert pure(u).recover(lambda x: pure(v)).run(None) == result.Ok(u)

    @given(st.text(), st.text())
    def test_not_catch_error(self, u: str, v: str) -> None:
        assert error(u).catch(lambda x: pure(v)).run(None) == result.Ok(v)

    @given(st.text())
    def test_panic(self, pan: str) -> None:
        assert panic(_MatchError(pan)).run(None) == result.Panic(_MatchError(pan))

    @given(st.text(), st.text())
    def test_on_failure_ok(self, u: str, v: str) -> None:
        assert pure(u).on_failure(lambda x: pure(v)).run(None) == result.Ok(u)

    @given(st.text(), st.text())
    def test_on_failure_error(self, u: str, v: str) -> None:
        assert error(u).map(lambda _: v).on_failure(pure).run(None) == result.Ok(
            result.Error(u)
        )

    @given(st.text(), st.text())
    def test_on_failure_panic(self, u: str, v: str) -> None:
        pu = _MatchError(u)
        assert panic(pu).map(lambda _: v).on_failure(pure).run(None) == result.Ok(
            result.Panic(pu)
        )

    @given(st.text())
    def test_read(self, i: st.integers()) -> None:
        assert read().run(i) == result.Ok(i)

    @given(st.text(), st.text())
    def test_map_read(self, u: str, v: str) -> None:
        assert read().contra_map_read(lambda x: x + v).run(u) == result.Ok(u + v)

    @given(st.text())
    def test_attempt_ok(self, u: str) -> None:
        assert pure(u).attempt().run(None) == result.Ok(result.Ok(u))

    @given(st.text())
    def test_attempt_error(self, u: str) -> None:
        assert error(u).attempt().run(None) == result.Ok(result.Error(u))

    @given(st.text())
    def test_attempt_panic(self, u: str) -> None:
        pu = _MatchError(u)
        assert panic(pu).attempt().run(None) == result.Ok(result.Panic(pu))

    @given(st.text())
    def test_from_ok(self, u: str) -> None:
        x = result.Ok(u)
        assert from_result(x).run(None) == x

    @given(st.text())
    def test_from_error(self, u: str) -> None:
        x = result.Error(u)
        assert from_result(x).run(None) == x

    @given(st.text())
    def test_from_panic(self, u: str) -> None:
        x = result.Panic(_MatchError(u))
        assert from_result(x).run(None) == x

    @given(st.integers(min_value=1000, max_value=2000))
    def test_defer(self, i: int) -> None:
        def f(j: int) -> IO[Any, Any, int]:
            if j <= 0:
                return pure(0)
            else:
                return defer_io(lambda: f(j - 1)).map(lambda x: x + 2)

        assert f(i).run(None) == result.Ok(2 * i)

    @given(st.integers(min_value=0, max_value=10))
    def test_recursion(self, i: int) -> None:
        def f(j: int) -> IO[Any, Any, int]:
            if j <= 0:
                return pure(0)
            else:
                return pure(j).flat_map(lambda x: f(j - 1).map(lambda y: x + y))

        assert f(i).run(None) == result.Ok(i * (i + 1) / 2) if i >= 0 else 0

    @given(st.lists(st.integers()))
    def test_traverse(self, l: List[int]) -> None:
        var = []

        def f(x: int) -> IO[None, None, int]:
            return defer(lambda: var.append(x)).then(pure(x * 2))

        assert traverse(l, f).run(None).map(list) == Ok([x * 2 for x in l])
        assert var == l
