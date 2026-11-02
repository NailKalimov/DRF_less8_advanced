"""Фильтрация, поиск и сортировка."""

from datetime import datetime

import pytest
from django.utils import timezone

from blog.models import Article

ARTICLES = "/api/articles/"


@pytest.fixture
def articles(john, mary, editor, make_article):
    data = [
        ("Django Tips", john, "2024-01-15", "Про ORM"),
        ("Learning Django", mary, "2024-03-10", "Первые шаги"),
        ("Python генераторы", john, "2024-06-01", "yield и next"),
        ("Asyncio", editor, "2025-02-20", "Это тоже про python"),
    ]
    created = {}
    for title, author, date, content in data:
        article = make_article(author, title, content=content)
        Article.objects.filter(pk=article.pk).update(
            created_at=timezone.make_aware(datetime.fromisoformat(date + "T12:00"))
        )
        created[title] = article
    make_article(john, "Черновик Django", published=False)
    return created


def titles(response):
    assert response.status_code == 200, response.data
    return [item["title"] for item in response.data["results"]]


def test_filter_by_author_and_published(api_client, articles, john):
    result = titles(api_client.get(ARTICLES, {"author": john.id, "published": "true"}))

    assert sorted(result) == ["Django Tips", "Python генераторы"]


def test_title_icontains(api_client, articles):
    assert sorted(titles(api_client.get(ARTICLES, {"title": "django"}))) == ["Django Tips", "Learning Django"]


def test_date_range(api_client, articles):
    result = titles(api_client.get(ARTICLES, {"created_after": "2024-02-01", "created_before": "2024-12-31"}))

    assert sorted(result) == ["Learning Django", "Python генераторы"]


def test_authors_multiple_choice_repeated_param(api_client, articles, mary, editor):
    result = titles(api_client.get(f"{ARTICLES}?authors={mary.id}&authors={editor.id}"))

    assert sorted(result) == ["Asyncio", "Learning Django"]


def test_authors_multiple_choice_rejects_comma_list(api_client, articles, mary, editor):
    """В методичке написано ?authors=1,3,5 — для ModelMultipleChoiceFilter это ошибка."""
    response = api_client.get(f"{ARTICLES}?authors={mary.id},{editor.id}")

    assert response.status_code == 400


def test_author_in_accepts_comma_list(api_client, articles, mary, editor):
    result = titles(api_client.get(f"{ARTICLES}?author_in={mary.id},{editor.id}"))

    assert sorted(result) == ["Asyncio", "Learning Django"]


def test_search_in_title_content_and_author(api_client, articles):
    assert sorted(titles(api_client.get(ARTICLES, {"search": "python"}))) == ["Asyncio", "Python генераторы"]
    assert sorted(titles(api_client.get(ARTICLES, {"search": "mary"}))) == ["Learning Django"]


def test_default_ordering_newest_first(api_client, articles):
    assert titles(api_client.get(ARTICLES)) == [
        "Asyncio",
        "Python генераторы",
        "Learning Django",
        "Django Tips",
    ]


def test_ordering_by_title(api_client, articles):
    assert titles(api_client.get(ARTICLES, {"ordering": "title"})) == [
        "Asyncio",
        "Django Tips",
        "Learning Django",
        "Python генераторы",
    ]


def test_ordering_by_unknown_field_is_ignored(api_client, articles):
    """Сортировать можно только по ordering_fields, остальное игнорируется."""
    assert titles(api_client.get(ARTICLES, {"ordering": "content"})) == titles(api_client.get(ARTICLES))


def test_filters_search_and_ordering_together(api_client, articles):
    result = titles(api_client.get(ARTICLES, {"search": "django", "published": "true", "ordering": "-created_at"}))

    assert result == ["Learning Django", "Django Tips"]
