from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.http import HttpResponse, HttpResponseNotAllowed

from blog.models import Post


def post_list(request):
    titles = Post.objects.filter(published=True).values_list("title", flat=True)
    body = "<html><body><ul>"
    body += "".join(f"<li>{title}</li>" for title in titles)
    body += "</ul></body></html>"
    return HttpResponse(body)


@login_required
def post_create(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    post = Post.objects.create(
        title=request.POST["title"],
        body=request.POST.get("body", ""),
        published=True,
    )
    send_mail(
        subject=f"New post: {post.title}",
        message=post.body,
        from_email="blog@example.com",
        recipient_list=["editor@example.com"],
    )
    return HttpResponse(status=201)
