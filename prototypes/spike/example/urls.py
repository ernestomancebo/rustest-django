from django.http import JsonResponse
from django.urls import path

from blog.models import Post


def index(request):
    return JsonResponse({"posts": Post.objects.count()})


urlpatterns = [path("", index)]
