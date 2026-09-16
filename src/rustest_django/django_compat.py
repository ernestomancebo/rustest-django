"""Every touch of Django's private (underscore-prefixed) test-case API lives
here, per ADR 0001, so a Django version bump has one place to adapt.
"""

from __future__ import annotations

import django.test


def build_test_case_class(
    *,
    transactional: bool,
    reset_sequences: bool,
    serialized_rollback: bool,
    databases: list[str] | None,
    available_apps: list[str] | None,
) -> type[django.test.TransactionTestCase]:
    """Build the throwaway TestCase subclass isolation is driven through.

    Skips TestCase's own setUpClass/tearDownClass for the non-transactional
    case: that machinery manages a class-level transaction we don't use, and
    closes connections in tearDownClass in a way that would break wrapping
    tests in our own isolation.
    """
    base = django.test.TransactionTestCase if transactional else django.test.TestCase
    _reset_sequences = reset_sequences
    _serialized_rollback = serialized_rollback
    _databases = databases
    _available_apps = available_apps

    class _RustestDjangoTestCase(base):  # ty: ignore[unsupported-base]
        reset_sequences = _reset_sequences
        serialized_rollback = _serialized_rollback
        if _databases is not None:
            databases = _databases
        if _available_apps is not None:
            available_apps = _available_apps

        if not transactional:

            @classmethod
            def setUpClass(cls) -> None:
                super(  # ty: ignore[unresolved-attribute]
                    django.test.TestCase, cls
                ).setUpClass()

            @classmethod
            def tearDownClass(cls) -> None:
                super(  # ty: ignore[unresolved-attribute]
                    django.test.TestCase, cls
                ).tearDownClass()

    return _RustestDjangoTestCase


def pre_setup(
    test_case_class: type[django.test.TransactionTestCase],
) -> django.test.TransactionTestCase:
    test_case_class.setUpClass()
    test_case = test_case_class(methodName="__init__")
    pre_setup_ran_eagerly = getattr(test_case_class, "_pre_setup_ran_eagerly", False)
    if not pre_setup_ran_eagerly:
        test_case._pre_setup()
    return test_case


def post_teardown(
    test_case: django.test.TransactionTestCase,
    test_case_class: type[django.test.TransactionTestCase],
) -> None:
    test_case._post_teardown()
    test_case_class.tearDownClass()
    test_case_class.doClassCleanups()
