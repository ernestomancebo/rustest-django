from django.http import HttpResponse

from feed.models import Article


async def article_list(request):
    titles = [title async for title in Article.objects.values_list("title", flat=True)]
    body = "<html><body><ul>"
    body += "".join(f"<li>{title}</li>" for title in titles)
    body += "</ul></body></html>"
    return HttpResponse(body)
