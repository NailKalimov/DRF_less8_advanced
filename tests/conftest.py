from io import BytesIO

import pytest
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from blog.models import Article
from blog.permissions import EDITORS_GROUP
from users.models import User

PASSWORD = "secret123"


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """Счётчики throttling живут в кеше: обнуляем их между тестами."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _media_root(settings, tmp_path):
    """Загруженные в тестах файлы пишем во временную папку."""
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture(autouse=True)
def _fast_password_hasher(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def make_user(db):
    def _make_user(username, *, verified=True, subscription="free", staff=False, editor=False):
        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password=PASSWORD,
            email_verified=verified,
            subscription_level=subscription,
            is_staff=staff,
        )
        if editor:
            group, _ = Group.objects.get_or_create(name=EDITORS_GROUP)
            user.groups.add(group)
        return user

    return _make_user


@pytest.fixture
def john(make_user):
    return make_user("john")


@pytest.fixture
def mary(make_user):
    return make_user("mary")


@pytest.fixture
def editor(make_user):
    return make_user("editor", editor=True, subscription="basic")


@pytest.fixture
def anna(make_user):
    """Email не подтверждён."""
    return make_user("anna", verified=False)


@pytest.fixture
def admin(make_user):
    return make_user("admin", staff=True, subscription="premium")


@pytest.fixture
def make_article(db):
    def _make_article(author, title="Статья", published=True, **kwargs):
        return Article.objects.create(
            title=title,
            content=kwargs.pop("content", f"Текст: {title}"),
            author=author,
            published=published,
            **kwargs,
        )

    return _make_article


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def png_file(name="cover.png", size=(800, 600), mode="RGBA"):
    """Картинка в памяти для загрузки. По умолчанию PNG с прозрачностью."""
    buffer = BytesIO()
    Image.new(mode, size, (10, 120, 200, 128) if mode == "RGBA" else (10, 120, 200)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")
