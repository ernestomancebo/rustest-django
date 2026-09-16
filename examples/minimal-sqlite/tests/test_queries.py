from blog.models import Post


def test_creating_a_post_takes_exactly_one_query(db, django_assert_num_queries):
    with django_assert_num_queries(1):
        Post.objects.create(title="counted")
