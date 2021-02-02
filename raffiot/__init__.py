from dataclasses import dataclass


@dataclass
class MatchError(Exception):
    message: str
