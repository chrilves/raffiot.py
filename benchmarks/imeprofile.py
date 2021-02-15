import cProfile, pstats
from raffiot import io
from raffiot.io import IO
import sys


def fibo_io(i: int) -> IO:
    if i > 1:
        return io.defer_io(fibo_io, i - 1).flat_map(
            lambda x: fibo_io(i - 2).map(lambda y: x + y)
        )
    else:
        return io.pure(i)


m = fibo_io(int(sys.argv[1]))


profiler = cProfile.Profile()
profiler.enable()
m.run(None)
profiler.disable()
stats = pstats.Stats(profiler).sort_stats("cumtime")
stats.print_stats()
