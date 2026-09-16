from django.http import HttpResponse

from rustest_django import asserts


def test_assert_contains_is_exposed_and_works() -> None:
    response = HttpResponse("<html>hello world</html>")
    asserts.assertContains(response, "hello world")
    asserts.assertNotContains(response, "goodbye")


def test_assert_query_set_equal_works(db) -> None:
    from dbapp.models import Thing

    Thing.objects.create(name="a")
    Thing.objects.create(name="b")

    asserts.assertQuerySetEqual(
        Thing.objects.order_by("name").values_list("name", flat=True),
        ["a", "b"],
    )


def test_assert_num_queries_assert_style_helper_is_exposed(db) -> None:
    assert hasattr(asserts, "assertNumQueries")


def test_all_expected_asserts_are_present() -> None:
    expected = {
        "assertContains",
        "assertNotContains",
        "assertRedirects",
        "assertTemplateUsed",
        "assertTemplateNotUsed",
        "assertFormError",
        "assertQuerySetEqual",
        "assertNumQueries",
        "assertHTMLEqual",
        "assertJSONEqual",
    }
    assert expected.issubset(set(asserts.__all__))
