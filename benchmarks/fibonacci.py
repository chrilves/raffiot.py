import sys
import statistics
from timeit import default_timer as timer
from raffiot import io
from raffiot.io import IO

n = int(sys.argv[1])
t = int(sys.argv[2])


def fibo(i: int) -> int:
    if i > 1:
        return fibo(i - 1) + fibo(i - 2)
    else:
        return i


def fibo_io(i: int) -> IO:
    if i > 1:
        return io.defer_io(fibo_io, i - 1).flat_map(
            lambda x: fibo_io(i - 2).map(lambda y: x + y)
        )
    else:
        return io.pure(i)


def mesure(nb):
    l = []
    i = 0
    while i < nb:
        start = timer()
        fibo(n)
        end = timer()
        l.append(end - start)
        i += 1
    return statistics.median(l)


def mesure_io(nb):
    l = []
    i = 0
    mio = fibo_io(n)
    while i < nb:
        start = timer()
        mio.run(None)
        end = timer()
        l.append(end - start)
        i += 1
    return statistics.median(l)


x = 8

print(f"fibo({x})=${fibo(x)}")
print(f"fibo_io({x})=${fibo_io(x).run(None).raise_on_panic()}")

print(f"fibo({n})    : {mesure(t)}")
print(f"fibo_io({n}) : {mesure_io(t)}")
print(f"fibo({n})    : {mesure(t)}")
print(f"fibo_io({n}) : {mesure_io(t)}")
