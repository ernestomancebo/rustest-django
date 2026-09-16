from __future__ import annotations

from typing import Any

import django.test
from rustest import fixture


class Settings:
    def __init__(self) -> None:
        object.__setattr__(self, "_to_restore", [])

    def __setattr__(self, attr: str, value: Any) -> None:
        override = django.test.override_settings(**{attr: value})
        override.enable()
        self._to_restore.append(override)

    def __delattr__(self, attr: str) -> None:
        from django.conf import settings as django_settings

        override = django.test.override_settings()
        override.enable()
        delattr(django_settings, attr)
        self._to_restore.append(override)

    def __getattr__(self, attr: str) -> Any:
        from django.conf import settings as django_settings

        return getattr(django_settings, attr)

    def _finalize(self) -> None:
        for override in reversed(self._to_restore):
            override.disable()
        del self._to_restore[:]


@fixture
def settings():
    wrapper = Settings()
    yield wrapper
    wrapper._finalize()
