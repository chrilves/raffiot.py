# Resource Management

Resource management is the safe creation and release
of resources: files, connection handlers, etc. Resource
management ensures all created resources will be released
this avoiding resource leaks.

Consider the code below accessing a database:

```python
>>> connection = connect_to_database()
>>> connection.exectute_sql_query(...)
>>> connection.close()
```

If the execution of the SQL query raise an exception, the
connection is never closed. Having too many unused connection
opened may forbid other parts of the code from creating new
connections, or may slow down the database or even crash
the application.

Fortunately Python has a built-in support for resource management
with the `with` syntax:

```python
>>> with connect_to_database() as connection:
...   connection.exectute_sql_query(...)
```

Sometimes the resource you want to create depends on another resource.
For example the connection configuration to the database could be
stored in a configuration file that need to be opened and closed:

```python
>>> with open_config_file() as file_content:
...   config = read_config(file_content)
...   with connect_to_database(config) as connection:
...     connection.exectute_sql_query(...)
```

Once again Python's `with`-statement covers this case nicely.
But there are two issues with Python's built-in resource management:

1. it is not trivial to pack two dependent resources into one.
2. it is not trivial to create your own resources.

This is where *Raffiot*'s resource management comes in.
Creating a `Resource` is as simple as providing a function to create
the resource and one to release it. You can also lift any Python's
"`with`-enabled" resource to *Raffiot*'s `Resource` by a single
function call.

`Resource` do compose very well too with the same API as `IO`.
In fact `Resource` is built upon `IO`. It has almost all of its
functionalities. Here are the imports for this section:


```python
>>> from raffiot import *
>>> from typing import Tuple, List, Any
```


Let's start by defining an `IO` that generates a random string
every time it runs:


```python
>>> import random
>>> import string
>>> rnd_str : IO[None, None, str] = (
...   io.defer(lambda:
...     ''.join(
...       random.choice(string.ascii_uppercase + string.digits)
...      for _ in range(8)
...     )
...   )
... )
>>> rnd_str.run(None)
Ok(success='CCQN80YY')
>>> rnd_str.run(None)
Ok(success='5JEOGVZS')
>>> rnd_str.run(None)
Ok(success='ZNLWSH1B')
>>> rnd_str.run(None)
Ok(success='MENS91RD')
```

## `from_open_close_io` : Creating a `Resource` from open/close `IO`s

The `Resource` we want to define will create and print a new string
every time it is used. Releasing it will simply be printing it.
A `Resource` is essentially two computations:

- one creating the resource
- one releasing the resource

Let's start by the `IO` creating and printing the string:

```python
>>> rs_open : IO[None, None, str] = (
...   rnd_str.flat_map(lambda s: io.sequence(
...     io.defer(print, f"Opening {s}"),
...     io.pure(s)
...   ))
... )
```

Now the function releasing the string (i.e. printing it):

```python
>>> def rs_close(s: str, cs: ComputationStatus) -> IO[None, None, None]:
...   return io.defer(print, f"Closing {s}")
```

The first function argument is the created resource. The second one indicates
whether the computation was successful. It can be either
`ComputationStatus.SUCCEEDED` or `ComputationStatus.FAILED`.

From there, creating a `Resource` is as simple as a single call
to `resource.from_open_close_io`:

```python
>>> rs : Resource[None,None,str] = resource.from_open_close_io(rs_open, rs_close)
```

That wasn't that hard, isn't it?

## `use` : using a resource

Now that we have a `Resource`, we want to use it. To do so, just
call the method `use`. You need to give it a function taking as
argument the resource created and retuning an `IO` that used this
resource. The result is an `IO`:

```python
>>> io_ok : IO[None,None,int] = rs.use(lambda s: io.pure(5))
>>> io_ok.run(None)
Opening B9G0G96J
Closing B9G0G96J
Ok(success=5)
```

As you can see a random string is created and released.
The result is an `IO` whose result is the result of the inner `IO`.

```python
>>> io_error : IO[None,None,Any] = rs.use(lambda s: io.error("Oups!"))
>>> io_error.run(None)
Opening R9A1YSJ3
Closing R9A1YSJ3
Error(error='Oups!')
```

If the inner `IO` fails, the string is still released!

```python
>>> io_panic : IO[None,None,None] = rs.use(lambda s: io.panic(Exception("BOOM!")))
>>> io_panic.run(None)
Opening PSUNW6M5
Closing PSUNW6M5
Panic(exception=Exception('BOOM!'))
```

If the inner `IO` panics, the string is still released too!

Note: the `with_(an_io)` method is a nice alias for `use(lambda _: an_io)`.

## `map`, `flat_map`, `defer`, `async_` and others.

`Resource` supports almost the same API as `IO`.
It includes `map`, `flat_map`, `defer`, `zip`, etc.
It means, for example, that you can create resources in parallel,
or simply create a list of resources (if one fails, all fails),
etc.

## `lift_io` : from `IO` to `Resource`

Actually, any `IO[E,E,A]` can be lifted into a `Resource[R,E,A]`.
The releasing function is just a no-op. It brings a lot of expressiveness
and safety to resource creation:

```python
>>> rs : Resource[None,None,None] = resource.lift_io(io.defer(print, "Hello World!"))
>>> rs.use(lambda none: io.pure(5)).run(None)
Hello World!
Ok(success=5)
```

## `from_open_close` : Resource from open and close functions

Sometimes it is easier to create a `Resource` from usual Python's
functions rather than from the open/close `IO`s. To do so, just
use the function `resource.from_open_close`:

```python
>>> def rs_open() -> str:
...   s = ''.join(
...     random.choice(string.ascii_uppercase + string.digits)
...     for _ in range(8)
...   )
...   print(f"Opening {s}")
...   return s
>>> def rs_close(s: str, cs: ComputationStatus) -> None:
...   print(f"Closing {s}")
>>> rs : Resource[None,None,str] = resource.from_open_close(rs_open, rs_close)
```

Once again, the he first argument of `rs_close` is the created resource and
the second one indicates whether the computation was successful:
`ComputationStatus.SUCCEEDED` or `ComputationStatus.FAILED`.

## `from_with` : Resource from `with`

If the resource you want to create already support Python's
`with`-statement, then you're lucky: you just have to make
one single call to `resource.from_with`

```python
>>> rs : Resource[None,None,str] = resource.from_with(io.defer(open, "hello.txt", "w"))
```

## Creating a Resource directly

A `Resource[R,E,A]` is essentially an
`IO[R,E,Tuple[A, Callable[[ComputationStatus], IO[R,E,Any]]]]`.
When the `IO` runs, it returns a pair
`Tuple[A, Callable[[ComputationStatus], IO[R,Any,Any]]]`.
The fist member of the pair is the created resource of type `A`.
The second member of the pair is the release function. Its argument is a
`ComputationStatus` indicating whether the computation was successful.
It must return an `IO` that perform the release of the resource.

Note that any failure encountered when releasing the resource makes the `IO`
to fail too.


```python
>>> create : IO[None,None,Tuple[str, IO[None,Any,Any]]] = (
...   rnd_str.flat_map(lambda filename:
...     io.defer(print, f"Opening {filename}").map(lambda file:
...       (file, lambda computationStatus: io.defer(print, f"Closing {filename}"))
...     )
...   )
... )
>>> rs : Resource[None,None,str] = Resource(create)
```


## Use Case : Temporary File

This is a complete use case of a `Resource` creating a random file.

```python
>>> from io import TextIOWrapper
>>> create : IO[None,None,Tuple[TextIOWrapper, IO[None,None,None]]] = (
...   rnd_str
...   .flat_map(lambda filename:
...     io.defer(print, f"Opening {filename}")
...     .then(io.defer(open, filename, "w"))
...     .map(lambda file:
...       ( file,
...         lambda computationStatus: io.defer(print, f"Closing {filename}")
...         .then(io.defer(file.close))
...       )
...     )
...    )
... )
>>> rs : Resource[None,None,TextIOWrapper] = Resource(create)
>>> io_ok : IO[None,None,None] = (
...   rs.use(lambda file:
...     io.defer(file.write, "Hello World!")
...   )
... )
>>> io_ok.run(None)
Opening 6E21M413
Closing 6E21M413
Ok(success=12)
>>> io_error : IO[None,None,None] = (
...   rs.use(lambda file:
...     io.defer(file.write, "Hello World!")
...     .then(io.error("Oups!"))
...   )
... )
>>> io_error.run(None)
Opening R9A1YSJ3
Closing R9A1YSJ3
Errors(errors=['Oups!'])
>>> io_panic : IO[None,None,None] = (
...   rs.use(lambda file:
...     io.defer(file.write, "Hello World!")
...     .then(io.panic(Exception("BOOM!")))
...   )
... )
>>> io_panic.run(None)
Opening R1V3A0SO
Closing R1V3A0SO
Panic(exceptions=[Exception('BOOM!')], errors=[])
```
