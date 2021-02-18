# Robust And Fast Functional IO Toolkit

*Raffiot* is small (almost) dependency-free python library providing some
usual functional tools. It currently provides
- an easy-to-use `IO` monad which is **stack-safe**, **fast**, support
  **asynchronous**, **concurrent**, **parallel** programming, has many other features.
- a `Resource` data type for easy but reliable **resource management**.
- a `Result` data structure to represent errors

## Demo

For a demo, just type this in a terminal:

```shell script
curl https://raw.githubusercontent.com/chrilves/raffiot.py/main/demos/raffiot_demo.sh | /bin/sh
```

This demo runs 4 computations in parallel. It demonstrates how simple concurrent
and parallel programing is in *raffiot*.

**Note that this command will install raffiot in your current Python environment**

## API Documentation

Not yet online, but easy to access, just open `docs/index.html`.

## Features

- *pure python*: *Raffiot* is written entirely in Python 3.7+.
- *small*: it is just a few small files.
- *(almost) dependency-free*: it only depends on `typing-extensions` (for the
  `@final` annotation).
- *crystal clear code*  

### IO

- *stack safe*: you just won't run into stack overflows anymore.
- *fast*: you won't notice the overhead.
- *context aware*: easy dependency injection and configuration propagation.
- *no None*: do you really like messages `'NoneType' object has to attribute xyz`?
- *no exceptions*: but clean error handling.
- *domain errors vs panics*: the API make a clear distinction between expected
  errors (that usually belongs to business domain) and unexpected errors
  (usually coming from bugs). Yes that's heavily inspired by *Rust*.

### Resource

Python has indeed the `with` construction, but `Resource` goes a step further.

- *easy user-defined resource creation*: just provide some open and close
  function.
- *composability*: the resource you want to create depends on another resource?
  Not a problem, you can compose resources the way you want. It scales.
- *error handling in resources*: `Resource` has everything `IO` has, including
  error management.

### Result

Very simple type, only 3 cases:

- `Ok(value)`: some value.
- `Error(error)`: some busyness domain error (you choose the error type!).
- `Panic(exception)`: when things go the unexpected way.





