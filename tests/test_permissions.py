"""Права доступа: встроенные и свои permissions."""

from .conftest import client_for

ARTICLES = "/api/articles/"


def titles(response):
    return {item["title"] for item in response.data["results"]}


def test_anonymous_can_read_but_not_create(api_client, john, make_article):
    make_article(john, "Публичная")

    assert api_client.get(ARTICLES).status_code == 200
    assert api_client.post(ARTICLES, {"title": "t", "content": "c"}, format="json").status_code == 401


def test_unverified_email_cannot_create(anna):
    response = client_for(anna).post(ARTICLES, {"title": "t", "content": "c"}, format="json")

    assert response.status_code == 403
    assert response.data["detail"] == "Вы должны подтвердить email для выполнения этого действия."


def test_author_is_taken_from_request(john, mary):
    response = client_for(john).post(
        ARTICLES, {"title": "Моя", "content": "c", "author": mary.id, "published": True}, format="json"
    )

    assert response.status_code == 201
    assert response.data["author"]["username"] == "john"
    # published только для чтения: публикация — через действие publish.
    assert response.data["published"] is False


def test_only_author_can_edit_and_delete(john, mary, make_article):
    article = make_article(john)
    url = f"{ARTICLES}{article.id}/"

    assert client_for(mary).patch(url, {"title": "чужая"}, format="json").status_code == 403
    assert client_for(mary).delete(url).status_code == 403
    assert client_for(john).patch(url, {"title": "моя"}, format="json").status_code == 200
    assert client_for(john).delete(url).status_code == 204


def test_unpublished_article_object_permission(api_client, john, mary, editor, make_article):
    draft = make_article(john, "Черновик", published=False)
    url = f"{ARTICLES}{draft.id}/"

    # Анониму DRF отвечает 401 («войдите»), вошедшему без прав — 403.
    assert api_client.get(url).status_code == 401
    assert client_for(mary).get(url).status_code == 403
    assert client_for(john).get(url).status_code == 200
    assert client_for(editor).get(url).status_code == 200


def test_list_hides_drafts_from_others(api_client, john, mary, editor, make_article):
    make_article(john, "Опубликована")
    make_article(john, "Черновик Джона", published=False)
    make_article(mary, "Черновик Мэри", published=False)

    assert titles(api_client.get(ARTICLES)) == {"Опубликована"}
    assert titles(client_for(john).get(ARTICLES)) == {"Опубликована", "Черновик Джона"}
    assert titles(client_for(editor).get(ARTICLES)) == {"Опубликована", "Черновик Джона", "Черновик Мэри"}


def test_pending_review_is_admin_only(john, admin, make_article):
    make_article(john, "Черновик", published=False)
    url = f"{ARTICLES}pending_review/"

    assert client_for(john).get(url).status_code == 403
    response = client_for(admin).get(url)
    assert response.status_code == 200
    assert titles(response) == {"Черновик"}


def test_publish_by_author_only(john, mary, make_article):
    draft = make_article(john, published=False)
    url = f"{ARTICLES}{draft.id}/publish/"

    assert client_for(mary).post(url).status_code == 403
    response = client_for(john).post(url)
    assert response.status_code == 200
    assert response.data == {"status": "article published"}
    draft.refresh_from_db()
    assert draft.published is True
