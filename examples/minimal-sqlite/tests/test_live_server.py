from http.client import HTTPConnection
from urllib.parse import urlsplit

from blog.models import Post


def test_live_server_reads_posts_created_by_test(live_server):
    Post.objects.create(title="Visible across threads", published=True)
    address = urlsplit(live_server.url)
    connection = HTTPConnection(address.netloc, timeout=5)
    try:
        connection.request("GET", "/")
        response = connection.getresponse()
        assert response.status == 200
        assert response.read() == (
            b"<html><body><ul><li>Visible across threads</li></ul></body></html>"
        )
    finally:
        connection.close()
