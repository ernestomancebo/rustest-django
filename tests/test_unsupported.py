import textwrap
from pathlib import Path

from _helpers import run_rustest
from rustest import FixtureRequest, parametrize, raises


@parametrize(
    "fixture_name,expected_snippets",
    [
        ("live_server", ("live_server", "unsupported in rustest-django v1")),
        (
            "django_db_serialized_rollback",
            ("django_db_serialized_rollback", "try db instead"),
        ),
        ("django_isolated_apps", ("django_isolated_apps",)),
    ],
)
def test_unsupported_fixture_fails_loudly(
    request: FixtureRequest, fixture_name: str, expected_snippets: tuple[str, ...]
) -> None:
    with raises(RuntimeError) as exc_info:
        request.getfixturevalue(fixture_name)

    message = str(exc_info.value)
    assert message.startswith("rustest-django: ")
    for snippet in expected_snippets:
        assert snippet in message


@parametrize(
    "marker_snippet,extra_assertion",
    [
        (
            """
            from rustest import mark


            @mark.urls("some.urls.module")
            def test_uses_urls_marker():
                assert True
            """,
            "Override settings.ROOT_URLCONF via the settings fixture",
        ),
        (
            """
            from rustest import mark


            @mark.ignore_template_errors
            def test_uses_ignore_template_errors_marker():
                assert True
            """,
            None,
        ),
    ],
)
def test_unsupported_marker_fails_loudly(
    tmp_path: Path, marker_snippet: str, extra_assertion: str | None
) -> None:
    (tmp_path / "conftest.py").write_text('rustest_fixtures = ["rustest_django"]\n')
    (tmp_path / "test_consumer.py").write_text(textwrap.dedent(marker_snippet))

    result = run_rustest(tmp_path)

    assert result.returncode != 0, result.stdout + result.stderr
    assert "1 failed" in result.stderr
    assert "rustest-django: " in result.stderr
    assert "unsupported in rustest-django v1" in result.stderr
    if extra_assertion is not None:
        assert extra_assertion in result.stderr
