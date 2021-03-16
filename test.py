from raffiot.io import *
from raffiot.result import Result, Ok, Error, Panic
from concurrent.futures import ThreadPoolExecutor
import time
from raffiot import MatchError

s = ""
l = ["a", "b", "c"]

with ThreadPoolExecutor() as pool:
    expected = s
    for u in l:
        expected += u

    def get_async(v, u):
        def f(r, k):
            def h():
                time.sleep(0.5)
                k(Ok(v + u))

            pool.submit(h)

        return async_(f)

    ret = pure(s)
    for u in l:
        ret = (lambda ret, u: ret.flat_map(lambda v: get_async(v, u)))(ret, u)

    x = ret.run(None, 1, 0.01).raise_on_panic()
    y = Ok(expected)
    print(f"x = {x}")
    print(f"y = {y}")
    assert x == y
