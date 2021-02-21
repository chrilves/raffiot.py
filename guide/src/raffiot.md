# Robust and Fast Functional IO Toolkit

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

## Documentation

### This [Guide](./index.html)

This guide will teach you how to use *Raffiot* through examples.
Just use the **left panel** or the **right arrow** on this page to jump to the next section.

### [API](./api/index.html)

The [API](./api/index.html) is online at
[https://chrilves.github.io/raffiot.py/api/index.html](./api/index.html).

## Features

- **pure python**: *Raffiot* is written entirely in Python 3.7+.
- **small**: it is just a few small files.
- **(almost) dependency-free**: it only depends on `typing-extensions` (for the
  `@final` annotation).
- **crystal clear code** 

### IO

- **stack safe**: you just won't run into stack overflows anymore.
- **fast**: you won't notice the overhead.
- **dependency injection** *made easy*: make some context visible from anywhere.
- *simple* **asynchronous** *and* **concurrent programming**: full support of synchronous,
  asynchronous and concurrent programming *with the same simple API*.
- **railway-oriented programming**: clean and simple failure management.
- **distinction** *between* **expected and unexpected failures**: some failures are part
  of your program's normal behaviour (errors) while others are show something
  terribly wrong happened (panics). Yes, that's heavily inspired by *Rust*.


### Resource

Python has the `with` construction, but `Resource` goes a step further.

- **easy user-defined resource creation**: just provide some open and close
  function.
- **composability**: the resource you want to create depends on another resource?
  Not a problem, you can compose resources the way you want. It scales.
- **failures handling in resources**: `Resource` has everything `IO` has, including
  its wonderful failure management.

### Result

Did I mention **Railway-Oriented Programming**? `Result` is represent the 3 possible
result of a computation:

- `Ok(value)`: the computation successfully computed the this `value`.
- `Error(error)`: the computation failed on some expected failure `error`, probably
   from the business domain.
- `Panic(exception)`: the computation failed on some unexpected failure `exception`.