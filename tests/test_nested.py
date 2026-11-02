"""Вложенные сериализаторы и оптимизация запросов."""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import serializers

from blog.models import Comment

from .conftest import client_for


def test_list_has_nested_author_without_comments(api_client, john, make_article):
    make_article(john)

    item = api_client.get("/api/articles/").data["results"][0]

    assert item["author"] == {"id": john.id, "username": "john", "first_name": "", "last_name": ""}
    assert "comments" not in item


def test_detail_has_comments_count_and_attachments(api_client, john, mary, make_article):
    article = make_article(john)
    Comment.objects.create(article=article, author=mary, text="Первый")
    Comment.objects.create(article=article, author=john, text="Второй")

    data = api_client.get(f"/api/articles/{article.id}/").data

    assert data["comments_count"] == 2
    assert [c["text"] for c in data["comments"]] == ["Первый", "Второй"]
    assert data["comments"][0]["author"]["username"] == "mary"
    assert data["attachments"] == []


def count_queries(client, url):
    with CaptureQueriesContext(connection) as ctx:
        assert client.get(url).status_code == 200
    return len(ctx.captured_queries)


def test_list_query_count_does_not_grow(api_client, john, mary, make_article):
    """select_related("author"): число запросов не зависит от числа статей (нет N+1)."""
    make_article(john, "1")
    few = count_queries(api_client, "/api/articles/")

    for i in range(8):
        make_article(mary if i % 2 else john, f"more {i}")
    many = count_queries(api_client, "/api/articles/")

    assert few == many


def test_detail_query_count_does_not_grow(api_client, john, mary, make_article):
    """prefetch_related("comments__author"): комментарии и авторы — фиксированным числом запросов."""
    article = make_article(john)
    Comment.objects.create(article=article, author=mary, text="1")
    few = count_queries(api_client, f"/api/articles/{article.id}/")

    for i in range(8):
        Comment.objects.create(article=article, author=mary if i % 2 else john, text=str(i))
    many = count_queries(api_client, f"/api/articles/{article.id}/")

    assert few == many


def test_comment_depth_expands_article(api_client, john, make_article):
    article = make_article(john, "Раскрытая статья")
    Comment.objects.create(article=article, author=john, text="Привет")

    comment = api_client.get("/api/comments/").data["results"][0]

    assert comment["article"]["title"] == "Раскрытая статья"
    assert comment["author"]["username"] == "john"
    assert "password" not in comment["author"]


def test_depth_without_explicit_author_leaks_password(john, make_article):
    """Почему в CommentDepthSerializer автор объявлен явно."""

    class NaiveDepthSerializer(serializers.ModelSerializer):
        class Meta:
            model = Comment
            fields = ["id", "text", "author"]
            depth = 1

    comment = Comment.objects.create(article=make_article(john), author=john, text="Привет")

    author = NaiveDepthSerializer(comment).data["author"]
    assert "password" in author
    assert "is_superuser" in author


def test_create_comment(john, make_article):
    article = make_article(john)

    response = client_for(john).post("/api/comments/", {"article": article.id, "text": "Отлично"}, format="json")

    assert response.status_code == 201
    assert response.data["author"]["username"] == "john"


def test_cannot_comment_unpublished_article(john, make_article):
    draft = make_article(john, published=False)

    response = client_for(john).post("/api/comments/", {"article": draft.id, "text": "?"}, format="json")

    assert response.status_code == 400
    assert "article" in response.data
