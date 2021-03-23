import sys
from time import time
from typing import Any, Callable
from multiprocessing import Pool
from dataclasses import dataclass

from raffiot import *

iterations: int = 10000000


def color(i: int, bright: bool) -> str:
    return f"\x1b[{i + (90 if bright else 30)}m"


reset = "\x1b[m"


def echo(x):
    pass


def prog(prog_index: int) -> IO[None, None, None]:
    """
    Print every number from `i` to 1.
    """

    name = chr(ord("A") + prog_index)
    col = color(prog_index % 6 + 1, prog_index >= 6)

    def the_io(j: int) -> IO[None, None, None]:
        if j > 0:
            return io.sequence(
                io.defer(echo, f"{col}From prog {name}: {j}{reset}"),
                io.yield_,
                io.defer_io(the_io, j - 1),
            )
        else:
            return io.pure(0)

    return the_io(iterations)


def prog_run(prog_index: int) -> Result[None, None]:
    return prog(prog_index).run(None, 1, 0)


def prog_in_pool(pool: Pool, prog_index: int) -> IO[Any, None, None]:
    return io.async_(
        lambda r, k: pool.apply_async(
            prog_run,
            args=(prog_index,),
            callback=k,
            error_callback=lambda x: k(Panic(x)),
        )
    )


# The main IO
main: IO[None, None, None] = io.defer(time).flat_map(
    lambda begin: resource.from_with(io.defer(Pool, 12))
    .use(
        lambda pool: io.parallel([prog_in_pool(pool, i) for i in range(12)]).flat_map(
            lambda fibers: io.wait(fibers).flat_map(lambda res: io.defer(print, res))
        )
    )
    .then(io.defer(time))
    .flat_map(lambda end: io.defer(print, f"finished in {end - begin} seconds."))
)

main.run(None, int(sys.argv[1]), float(sys.argv[2])).raise_on_panic()
