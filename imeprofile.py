import cProfile, pstats
from raffiot import io
from raffiot.io import IO
import sys
import time

# Colors in termainal
reset = "\u001b[m"
bred = "\u001b[91m"
bgreen = "\u001b[92m"
byellow = "\u001b[93m"
bcyan = "\u001b[96m"


def echo(x):
    pass


def prog(color, name, i) -> IO[None, None, None]:
    """
    Print in `color` every number from `i` to 1.
    """
    if i > 0:
        return io.defer(print, f"{color}From prog {name}: {i}{reset}").then(
            io.yield_(), io.defer_io(prog, color, name, i - 1)
        )
    else:
        return io.pure(0)


# The main IO
main: IO[None, None, None] = io.defer(time.time).flat_map(
    lambda start: io.parallel(
        prog(bred, "A", 100000),
        prog(bgreen, "B", 100000),
        prog(byellow, "C", 100000),
        prog(bcyan, "D", 100000),
    )
    .flat_map(lambda fibers: io.wait(fibers))
    .then(io.defer(time.time))
    .flat_map(lambda end: io.defer(print, f"finished in {end - start} seconds"))
)

profiler = cProfile.Profile()
profiler.enable()
main.run(None, int(sys.argv[1]), float(sys.argv[2]))
profiler.disable()
stats = pstats.Stats(profiler).sort_stats("cumtime")
stats.print_stats()
