"""Работа с файлами: обложка, миниатюра и вложения."""

from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from blog.models import ArticleAttachment

from .conftest import client_for, png_file


def test_upload_cover_creates_thumbnail(john, make_article, settings):
    article = make_article(john)

    response = client_for(john).post(
        f"/api/articles/{article.id}/upload_cover/", {"cover_image": png_file()}, format="multipart"
    )

    assert response.status_code == 200, response.data
    assert response.data["cover_image_url"].startswith("http://testserver/media/articles/covers/")
    assert response.data["cover_thumbnail_url"].startswith("http://testserver/media/articles/thumbnails/")

    article.refresh_from_db()
    with Image.open(Path(settings.MEDIA_ROOT) / article.cover_thumbnail.name) as thumbnail:
        assert thumbnail.format == "JPEG"
        assert max(thumbnail.size) <= 300


def test_reupload_cover_deletes_old_file(john, make_article, settings):
    article = make_article(john)
    client = client_for(john)
    url = f"/api/articles/{article.id}/upload_cover/"

    client.post(url, {"cover_image": png_file("one.png")}, format="multipart")
    article.refresh_from_db()
    old_cover = Path(settings.MEDIA_ROOT) / article.cover_image.name
    old_thumb = Path(settings.MEDIA_ROOT) / article.cover_thumbnail.name

    client.post(url, {"cover_image": png_file("two.png")}, format="multipart")

    assert not old_cover.exists()
    assert not old_thumb.exists()


def test_create_article_with_cover_in_multipart(john):
    response = client_for(john).post(
        "/api/articles/",
        {"title": "С обложкой", "content": "...", "cover_image": png_file(mode="RGB")},
        format="multipart",
    )

    assert response.status_code == 201, response.data
    assert response.data["cover_thumbnail_url"] is not None


def test_upload_cover_without_file(john, make_article):
    article = make_article(john)

    response = client_for(john).post(f"/api/articles/{article.id}/upload_cover/", {}, format="multipart")

    assert response.status_code == 400
    assert "cover_image" in response.data


@pytest.mark.parametrize(
    "upload",
    [
        SimpleUploadedFile("cover.png", b"not an image", content_type="image/png"),
        SimpleUploadedFile("cover.gif", b"GIF89a", content_type="image/gif"),
    ],
    ids=["not-an-image", "wrong-extension"],
)
def test_upload_cover_rejects_bad_files(john, make_article, upload):
    article = make_article(john)

    response = client_for(john).post(
        f"/api/articles/{article.id}/upload_cover/", {"cover_image": upload}, format="multipart"
    )

    assert response.status_code == 400


def test_only_author_can_upload_cover(john, mary, make_article):
    article = make_article(john)

    response = client_for(mary).post(
        f"/api/articles/{article.id}/upload_cover/", {"cover_image": png_file()}, format="multipart"
    )

    assert response.status_code == 403


def test_add_attachment(john, make_article):
    article = make_article(john)
    upload = SimpleUploadedFile("notes.txt", b"hello", content_type="text/plain")

    response = client_for(john).post(
        f"/api/articles/{article.id}/add_attachment/", {"file": upload}, format="multipart"
    )

    assert response.status_code == 201, response.data
    assert response.data["filename"] == "notes.txt"
    assert response.data["file_size"] == 5
    assert response.data["file_url"].startswith("http://testserver/media/articles/attachments/")


def test_add_attachment_custom_filename(john, make_article):
    article = make_article(john)
    upload = SimpleUploadedFile("a.pdf", b"%PDF-1.4", content_type="application/pdf")

    response = client_for(john).post(
        f"/api/articles/{article.id}/add_attachment/",
        {"file": upload, "filename": "Важный документ.pdf"},
        format="multipart",
    )

    assert response.data["filename"] == "Важный документ.pdf"


def test_add_attachment_rejects_extension(john, make_article):
    article = make_article(john)
    upload = SimpleUploadedFile("virus.exe", b"MZ", content_type="application/octet-stream")

    response = client_for(john).post(
        f"/api/articles/{article.id}/add_attachment/", {"file": upload}, format="multipart"
    )

    assert response.status_code == 400
    assert "file" in response.data


def test_add_attachment_rejects_large_file(john, make_article):
    article = make_article(john)
    upload = SimpleUploadedFile("big.txt", b"x" * (5 * 1024 * 1024 + 1), content_type="text/plain")

    response = client_for(john).post(
        f"/api/articles/{article.id}/add_attachment/", {"file": upload}, format="multipart"
    )

    assert response.status_code == 400
    assert "5 МБ" in str(response.data["file"])


def test_detail_lists_attachments(api_client, john, make_article):
    article = make_article(john)
    client_for(john).post(
        f"/api/articles/{article.id}/add_attachment/",
        {"file": SimpleUploadedFile("n.txt", b"1", content_type="text/plain")},
        format="multipart",
    )

    data = api_client.get(f"/api/articles/{article.id}/").data

    assert [a["filename"] for a in data["attachments"]] == ["n.txt"]


def test_orm_create_skips_model_validators(john, make_article):
    """Почему add_attachment идёт через сериализатор, а не через objects.create()."""
    upload = SimpleUploadedFile("virus.exe", b"MZ", content_type="application/octet-stream")

    attachment = ArticleAttachment.objects.create(article=make_article(john), file=upload, filename="virus.exe")

    assert attachment.pk is not None  # ORM пропустил .exe
    with pytest.raises(ValidationError):
        attachment.full_clean()  # а валидаторы модели его бы отклонили
