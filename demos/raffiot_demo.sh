#!/bin/sh
pip install -U raffiot && \
python -c '
from raffiot import io
from raffiot.io import IO

# Colors in termainal
reset = "\u001b[m"
bred = "\u001b[91m"
bgreen = "\u001b[92m"
byellow = "\u001b[93m"
bcyan = "\u001b[96m"

def prog(color, name, i) -> IO[None, None, None]:
    """
    Print in `color` every number from `i` to 1.
    """
    if i > 0:
        return (
          io.defer(print, f"{color}From prog {name}: {i}{reset}")
            .then(
              io.yield_(),
              io.defer_io(prog, color, name, i - 1)
            )
          )
    else:
        return io.pure(0)

#The main IO
main: IO[None, None, None] = (
    io.parallel(
        prog(bred, "A", 10000),
        prog(bgreen, "B", 10000),
        prog(byellow, "C", 10000),
        prog(bcyan, "D", 10000),
    )
    .flat_map(lambda fibers: io.wait(fibers))
    .then(io.defer(print, "finished"))
)

main.run(None)
'