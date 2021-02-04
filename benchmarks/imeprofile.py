import cProfile, pstats
from raffiot import io
from raffiot.io import IO
import sys


def fibo_io(u0: int, u1: int, i: int) -> IO:
    if i > 1:
        return io.defer_io(lambda: fibo_io(u1, (u0 + u1) % 10000, i - 1))
    if i == 1:
        return io.pure(u1)
    return io.pure(u0)


m = fibo_io(0, 1, int(sys.argv[1]))


profiler = cProfile.Profile()
profiler.enable()
m.run(None)
profiler.disable()
stats = pstats.Stats(profiler).sort_stats("cumtime")
stats.print_stats()
