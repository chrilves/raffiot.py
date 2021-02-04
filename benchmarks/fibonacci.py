import sys
import statistics
from timeit import default_timer as timer
from raffiot import io
from raffiot.io import IO

n = int(sys.argv[1])
t = int(sys.argv[2])


def fibo(u0: int, u1: int, i: int) -> int:
    if i > 1:
        return fibo(u1, u0 + u1, i - 1)
    if i == 1:
        return u1
    return u0


def fibo_io(u0: int, u1: int, i: int) -> IO:
    if i > 1:
        return io.defer_io(lambda: fibo_io(u1, u0 + u1, i - 1))
    if i == 1:
        return io.pure(u1)
    return io.pure(u0)


def mesure(nb):
    l = []
    i = 0
    while i < 10 * nb:
        start = timer()
        fibo(0, 1, n)
        end = timer()
        l.append(end - start)
        i += 1
    return statistics.median(l)


def mesure_io(nb):
    l = []
    i = 0
    mio = fibo_io(0, 1, n)
    while i < nb:
        start = timer()
        mio.run(None)
        end = timer()
        l.append(end - start)
        i += 1
    return statistics.median(l)


print(io.marker)
print(f"fibo({n})    : {mesure(t)}")
print(f"fibo_io({n}) : {mesure_io(t)}")
print(f"fibo({n})    : {mesure(t)}")
print(f"fibo_io({n}) : {mesure_io(t)}")
