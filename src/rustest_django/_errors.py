from __future__ import annotations


class ConfigError(Exception):
    pass


def _message(body: str) -> str:
    return f"rustest-django: {body}"
