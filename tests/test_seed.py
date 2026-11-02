"""Команда seed_demo готовит данные для демонстрации."""

from io import StringIO

from django.contrib.auth.models import Group
from django.core.management import call_command

from blog.models import Article, ArticleAttachment, Comment
from users.models import User


def seed():
    call_command("seed_demo", stdout=StringIO())


def test_seed_demo_creates_demo_data(db):
    seed()

    assert set(User.objects.values_list("username", flat=True)) == {"admin", "john", "editor", "anna", "premium"}
    assert User.objects.get(username="john").check_password("secret123")
    assert not User.objects.get(username="anna").email_verified
    assert Group.objects.get(name="Editors").user_set.filter(username="editor").exists()

    assert Article.objects.filter(published=True).count() == 25
    assert Article.objects.filter(published=False).count() == 3
    assert Comment.objects.exists()
    assert ArticleAttachment.objects.count() == 1

    with_covers = Article.objects.exclude(cover_image="").order_by("id")
    assert all(article.cover_thumbnail for article in with_covers)
    # Статьям с обложками save() не должен вернуть сегодняшнюю дату.
    assert [a.created_at.date().isoformat() for a in with_covers] == ["2024-01-10", "2024-02-14", "2024-03-20"]

    dates = list(Article.objects.values_list("created_at", flat=True))
    assert len(set(dates)) == len(dates)


def test_seed_demo_can_run_twice(db):
    seed()
    seed()

    assert User.objects.count() == 5
    assert Article.objects.count() == 28
