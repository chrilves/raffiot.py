# Context

The time has come to talk about the third type parameter of an `IO`.
**In the type `IO[R,E,A]`, `R` is the type of the context**.
The context is a value that is always accessible to any `IO`.
You can think of it as a local global variable.
I assure you this sentence make sense!

## `run` : executing an `IO` in a given context.

We have called the method `run` many times. And every time we gave it
`None` as argument. The argument you give to `run` is actually the
context value. You take any value you want as the context.
Usually the context is a value you want to be accessible from everywhere.

Global variables are indeed accessible from everywhere but they
are very annoying because they can only have one value at a time.
Furthermore every change made to the global variable by a part of
your code will affect all other parts reading this global variable.

On the opposite side, local variable are nice because every part
of your code can have its own dedicated local variable. But they
are annoying because to make them accessible everywhere, you have
to pass it to every functions as parameters. This is error prone and pollutes your code.

Given an `IO` named `main`, when you call `run` with some context `r`,
the value `r` is accessible from everywhere in `main`.
The context behaves like a global variable inside the running `IO`.
But you can pass every call to `run` a different context.
The context behaves like a local variable between different calls to `run`.

## `read` : accessing the shared context.

To access the context, just call the function `io.read`. Its result
is the context:

```python
>>> main : IO[int,None,int] = io.read
>>> main.run(5)
Ok(success=5)
>>> main.run(77)
Ok(success=77)
```

This example is indeed trivial. But imagine that `main` can be
a very big program. You can call `io.read` anywhere in `main` to
get the context. It saves you the huge burden of passing the context
from `run` to every function until it reaches the location of `io.read`.


## `contra_map_read` : transforming the shared context.

As I said, the context behaves as a local global variable.
With `io.read` you have seen its global behaviour.
The method `contra_map_read` transforms the context, but only
for the `IO` it is being called on.
Note that the context is transformed before the `IO` is executed.

The method `contra_map_read` is very useful when you need to
alter the context. For example, your program may start with `None`
as context, read its configuration to instantiate the services it wants
to inject and then change to context to pass these services everywhere
for dependency injection.


```python
>>> main : IO[str,None,int] = io.read.contra_map_read(lambda s: len(s))
>>> main.run("Hello")
Ok(success=5)
```

## `defer_read` : doing something context-dependent later.

The function `io.defer_read` is useful when you it is easier to
implement an `IO` as a normal function and then transform it into an `IO`.
`io.defer_read`, like `io.defer`, takes as first argument the function
you want to execute later. But unlike `io.defer`, this function:

- has access to the context
- returns a `Result[E,A]`

The last point is important because it means the function can raise
errors while `io.defer` can only raise panics.

```python
>>> def f(context:int, i: int) -> Result[str,int]:
...   if context > 0:
...     return Ok(context + i)
...   else:
...     return Error("Ooups!")
>>> main : IO[int,None,int] = io.defer_read(f, 5)
>>> main.run(10)
Ok(success=15)
>>> main.run(-1)
Error(error='Ooups!')
```

## `defer_read_io` : computing a context-dependent IO later. 

The function `io.defer_read_io` is the `IO` counterpart of
`io.defer_read`. It is useful when the context-aware function you want
to execute later returns an `IO`.


```python
>>> def f(context:int, i:int) -> IO[None,str,int]:
...   if context > 0:
...     return io.pure(context + i)
...   else:
...     return io.error("Ooups!")
>>> main : IO[int,None,int] = io.defer_read_io(f, 5)
>>> main.run(10)
Ok(success=15)
>>> main.run(-1)
Error(error='Ooups!')
```

## Use Case: Dependency Injection

As a demonstration of how dependency injection works in *Raffiot*,
create and fill the file `dependency_injection.py` as below:

```python
from raffiot import *

import sys
from dataclasses import dataclass
from typing import List

@dataclass
class NotFound(Exception):
  url: str

class Service:
  def get(self, path: str) -> IO[None,NotFound,str]:
    pass

class HttpService(Service):
  def __init__(self, host: str, port: int) -> None:
    self.host = host
    self.port = port
  
  def get(self, path: str) -> IO[None,NotFound,str]:
    url = f"http://{self.host}:{self.port}/{path}"

    if path == "index.html":
      response = io.pure(f"HTML Content of url {url}")
    elif path == "index.md":
      response = io.pure(f"Markdown Content of url {url}")
    else:
      response = io.error(NotFound(url))
    return io.defer(print, f"Opening url {url}").then(response)

class LocalFileSytemService(Service):
  def get(self, path: str) -> IO[None,NotFound,str]:
    url = f"/{path}"

    if path == "index.html":
      response = io.pure(f"HTML Content of file {url}")
    elif path == "index.md":
      response = io.pure(f"Markdown Content of file {url}")
    else:
      response = io.error(NotFound(url))
    return io.defer(print, f"Opening file {url}").then(response)


main : IO[Service,NotFound,List[str]] = (
  io.read
  .flat_map(lambda service:
    service.get("index.html")
    .flat_map(lambda x:
      service.get("index.md")
      .flat_map(lambda y: io.defer(print, "Result = ", [x,y]))
    )
  )
)

if len(sys.argv) >= 2 and sys.argv[1] == "http":
  service = HttpService("localhost", 80)
else:
  service = LocalFileSytemService()

main.run(service)
```

Running the program with the `HTTPService` gives:

```shell
$ python dependency_injection.py http
Opening url http://localhost:80/index.html
Opening url http://localhost:80/index.md
Result =  ['HTML Content of url http://localhost:80/index.html', 'Markdown Content of url http://localhost:80/index.md']
```

While running it with the `LocalFileSytemService` gives:

```shell
$ python dependency_injection.py localfs
Opening file /index.html
Opening file /index.md
Result =  ['HTML Content of file /index.html', 'Markdown Content of file /index.md']
```

Once again, `main` is still a very short `IO`, so it may be not trivial
how much the context is a life saver. But imagine the `main` `IO` to be
one of your real program. It would be much bigger, and passing the
context as global or local variables would be a much bigger problem.