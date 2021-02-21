from raffiot import io
from raffiot.io import IO

import sys
from dataclasses import dataclass
from typing import List


@dataclass
class NotFound(Exception):
    url: str


class Service:
    def get(self, path: str) -> IO[None, NotFound, str]:
        pass


class HttpService(Service):
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

    def get(self, path: str) -> IO[None, NotFound, str]:
        url = f"http://{self.host}:{self.port}/{path}"

        if path == "index.html":
            response = io.pure(f"HTML Content of url {url}")
        elif path == "index.md":
            response = io.pure(f"Markdown Content of url {url}")
        else:
            response = io.error(NotFound(url))
        return io.defer(print, f"Opening url {url}").then(response)


class LocalFileSytemService(Service):
    def get(self, path: str) -> IO[None, NotFound, str]:
        url = f"/{path}"

        if path == "index.html":
            response = io.pure(f"HTML Content of file {url}")
        elif path == "index.md":
            response = io.pure(f"Markdown Content of file {url}")
        else:
            response = io.error(NotFound(url))
        return io.defer(print, f"Opening file {url}").then(response)


main: IO[Service, NotFound, List[str]] = io.read().flat_map(
    lambda service: service.get("index.html").flat_map(
        lambda x: service.get("index.md").flat_map(
            lambda y: io.defer(print, "Result = ", [x, y])
        )
    )
)

if len(sys.argv) >= 2 and sys.argv[1] == "http":
    service = HttpService("localhost", 80)
else:
    service = LocalFileSytemService()

main.run(service)
