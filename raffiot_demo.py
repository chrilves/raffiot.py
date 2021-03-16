from raffiot import io
from raffiot.io import IO
from raffiot.result import Ok, Error, Panic, Result
import sys
import time

# Colors in termainal
reset = "\u001b[m"
bred = "\u001b[91m"
bgreen = "\u001b[92m"
byellow = "\u001b[93m"
bcyan = "\u001b[96m"


def echo(x):
    print(x)


def prog(color, name, i) -> IO[None, None, None]:
    """
    Print in `color` every number from `i` to 1.
    """
    if i > 0:
        return io.defer(echo, f"{color}From prog {name}: {i}{reset}").then(
            io.yield_(), io.defer_io(prog, color, name, i - 1)
        )
    else:
        return io.pure(0)


cont = None


def store(r, k):
    global cont
    print("Storing cont")
    cont = k


def resume():
    print("Resuming")
    try:
        cont(Ok(None))
    except Exception as exn:
        print(f"OOps {exn}")
        raise exn


def finished(start):
    global cont
    return io.defer(print, "retreiveing cont").then(
        io.defer(resume)
        .then(io.defer(time.time))
        .flat_map(lambda end: io.defer(print, f"finished in {end - start} seconds"))
    )


# The main IO
main: IO[None, None, None] = io.parallel(io.async_(store)).then(
    io.defer(time.time).flat_map(
        lambda start: io.parallel(
            prog(bred, "A", 10000),
            prog(bgreen, "B", 10000),
            prog(byellow, "C", 10000),
            prog(bcyan, "D", 10000),
        )
        .flat_map(lambda fibers: io.wait(fibers))
        .then(finished(start))
    )
)

main.run(None, int(sys.argv[1]), float(sys.argv[2])).raise_on_panic()
