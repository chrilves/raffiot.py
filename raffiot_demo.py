import sys
from time import time
from typing import Any

from raffiot import *

iterations: int = 10000000)


def color(i: int, bright: bool) -> str:
    return f"\x1b[{i + (90 if bright else 30)}m"


reset = "\x1b[m"


def echo(x):
    pass


def prog(prg_index: int) -> IO[None, None, None]:
    """
    Print every number from `i` to 1.
    """

    name = chr(ord("A") + prg_index)
    col = color(prg_index % 6 + 1, prg_index >= 6)

    def the_io(j: int) -> IO[None, None, None]:
        if j > 0:
            return io.sequence(
                io.defer(echo, f"{col}From prog {name}: {j}{reset}"),
                io.yield_,
                io.defer_io(the_io, j - 1),
            )
        else:
            return io.pure(None)

    return the_io(iterations)


# The main IO
main: IO[None, None, None] = io.defer(time).flat_map(
    lambda begin: io.parallel([prog(i) for i in range(12)])
    .flat_map(lambda fibers: io.wait(fibers))
    .then(io.defer(time))
    .flat_map(lambda end: io.defer(print, f"finished in {end - begin} seconds."))
)

main.run(None, int(sys.argv[1]), float(sys.argv[2])).raise_on_panic()
