"""Пагинация: номера страниц, limit/offset и курсор."""

from datetime import timedelta

from django.utils import timezone

from blog.models import Article, Comment


def create_articles(author, count):
    now = timezone.now()
    Article.objects.bulk_create(
        Article(title=f"Статья {i:03d}", content="...", author=author, published=True) for i in range(count)
    )
    # Разные даты, чтобы порядок был однозначным.
    for index, article in enumerate(Article.objects.order_by("id")):
        Article.objects.filter(pk=article.pk).update(created_at=now - timedelta(minutes=index))


def test_page_number_pagination(api_client, john):
    create_articles(john, 25)

    first = api_client.get("/api/articles/")
    assert first.data["count"] == 25
    assert len(first.data["results"]) == 10
    assert first.data["previous"] is None
    assert "page=2" in first.data["next"]

    third = api_client.get("/api/articles/", {"page": 3})
    assert len(third.data["results"]) == 5
    assert third.data["next"] is None


def test_client_controls_page_size_with_cap(api_client, john):
    create_articles(john, 120)

    assert len(api_client.get("/api/articles/", {"page_size": 25}).data["results"]) == 25
    # max_page_size = 100 не даёт запросить больше.
    assert len(api_client.get("/api/articles/", {"page_size": 1000}).data["results"]) == 100


def test_limit_offset_pagination_on_comments(api_client, john, make_article):
    article = make_article(john)
    for i in range(15):
        Comment.objects.create(article=article, author=john, text=f"Комментарий {i}")

    response = api_client.get("/api/comments/", {"limit": 5, "offset": 10})

    assert response.data["count"] == 15
    assert [c["text"] for c in response.data["results"]] == [f"Комментарий {i}" for i in range(10, 15)]


def test_cursor_pagination_on_feed(api_client, john):
    create_articles(john, 25)

    first = api_client.get("/api/feed/")
    assert "count" not in first.data
    assert "cursor=" in first.data["next"]
    assert first.data["previous"] is None

    seen = [a["id"] for a in first.data["results"]]
    url = first.data["next"]
    while url:
        page = api_client.get(url)
        seen += [a["id"] for a in page.data["results"]]
        url = page.data["next"]

    assert len(seen) == len(set(seen)) == 25


def test_cursor_is_stable_when_new_articles_appear(api_client, john):
    create_articles(john, 15)
    first = api_client.get("/api/feed/")
    first_ids = [a["id"] for a in first.data["results"]]

    # Новая статья появилась между запросами страниц.
    Article.objects.create(title="Свежая", content="...", author=john, published=True)

    second_ids = [a["id"] for a in api_client.get(first.data["next"]).data["results"]]
    assert not set(first_ids) & set(second_ids)
    assert len(first_ids) + len(second_ids) == 15
