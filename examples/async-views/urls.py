from django.urls import path

from feed import views

urlpatterns = [
    path("", views.article_list, name="article-list"),
]
