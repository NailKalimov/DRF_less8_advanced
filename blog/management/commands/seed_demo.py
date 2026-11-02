"""Заполняет базу данными для демонстрации: python manage.py seed_demo.

Команду можно запускать повторно: статьи и комментарии пересоздаются,
пароли демо-пользователей сбрасываются на известные значения.
"""

from datetime import datetime, timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from blog.models import Article, ArticleAttachment, Comment
from blog.permissions import EDITORS_GROUP

User = get_user_model()

# Пароли простые: проект только для локальной демонстрации.
DEMO_USERS = [
    # username, password, email_verified, subscription, is_staff, is_superuser, editor
    ("admin", "admin123", True, "premium", True, True, False),
    ("john", "secret123", True, "free", False, False, False),
    ("editor", "editor123", True, "basic", False, False, True),
    ("anna", "anna12345", False, "free", False, False, False),
    ("premium", "premium123", True, "premium", False, False, False),
]

PUBLISHED_TITLES = [
    ("Введение в Django REST Framework", "john"),
    ("Django ORM: select_related и prefetch_related", "editor"),
    ("Python: генераторы и итераторы", "premium"),
    ("JWT против сессий: что выбрать", "john"),
    ("Пагинация в API: page, offset, cursor", "editor"),
    ("Тестирование API с pytest", "premium"),
    ("PostgreSQL для Django-разработчика", "john"),
    ("Асинхронный Python: asyncio на практике", "admin"),
    ("Docker для Python-проекта", "editor"),
    ("Фильтрация данных с django-filter", "john"),
    ("Throttling: защищаем API от перегрузки", "premium"),
    ("Права доступа в DRF", "john"),
    ("Загрузка файлов через API", "editor"),
    ("Celery и фоновые задачи", "admin"),
    ("Кеширование в Django", "premium"),
    ("Типизация в Python: mypy", "john"),
    ("FastAPI или Django: сравнение", "editor"),
    ("Git для командной работы", "premium"),
    ("Чистая архитектура в Django-проектах", "john"),
    ("Логирование в Python", "admin"),
    ("Django Admin: тонкая настройка", "editor"),
    ("Работа с датами и часовыми поясами", "premium"),
    ("Сериализаторы DRF изнутри", "john"),
    ("Python 3.13: что нового", "editor"),
    ("REST API: проектирование эндпоинтов", "premium"),
]

DRAFT_TITLES = [
    ("Черновик: GraphQL в Django", "john"),
    ("Черновик: оптимизация запросов", "editor"),
    ("Черновик: WebSocket и Django Channels", "premium"),
]

COMMENTS = [
    "Спасибо, очень полезно!",
    "А как это работает с PostgreSQL?",
    "Добавьте, пожалуйста, пример с тестами.",
    "Попробовал на своём проекте — всё работает.",
    "Не совсем понял про последний пример.",
]


def demo_cover(text: str, color: tuple[int, int, int], name: str) -> ContentFile:
    """Рисует обложку 1200×630 в PNG с прозрачностью (режим RGBA).

    Прозрачность нарочно: на ней видно, зачем make_thumbnail
    переводит картинку в RGB перед сохранением в JPEG.
    """
    image = Image.new("RGBA", (1200, 630), (*color, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((60, 60, 1140, 570), outline=(255, 255, 255, 255), width=8)
    draw.ellipse((900, 380, 1100, 580), fill=(255, 255, 255, 96))
    draw.text((100, 100), text, fill=(255, 255, 255, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return ContentFile(buffer.getvalue(), name=name)


class Command(BaseCommand):
    help = "Создаёт демо-пользователей, статьи, комментарии, обложки и вложения."

    @transaction.atomic
    def handle(self, *args, **options):
        editors, _ = Group.objects.get_or_create(name=EDITORS_GROUP)

        users = {}
        for username, password, verified, subscription, staff, superuser, editor in DEMO_USERS:
            user, _ = User.objects.get_or_create(username=username)
            user.email = f"{username}@example.com"
            user.email_verified = verified
            user.subscription_level = subscription
            user.is_staff = staff
            user.is_superuser = superuser
            user.set_password(password)
            user.save()
            if editor:
                user.groups.add(editors)
            users[username] = user

        Article.objects.all().delete()

        articles = []
        all_titles = [(t, a, True) for t, a in PUBLISHED_TITLES] + [(t, a, False) for t, a in DRAFT_TITLES]
        for title, author, published in all_titles:
            articles.append(
                Article.objects.create(
                    title=title,
                    content=f"{title}. Демо-текст статьи для урока по Django REST Framework.",
                    author=users[author],
                    published=published,
                )
            )

        # Обложки: присваиваем файл полю и сохраняем, Article.save() сделает миниатюру.
        # Не article.cover_image.save(...): этот метод сначала пишет файл
        # в хранилище, и save() модели уже не увидит новую обложку.
        for article, color in zip(articles[:3], [(37, 99, 235), (22, 163, 74), (219, 39, 119)]):
            label = f"DRF demo: article #{article.pk}"
            article.cover_image = demo_cover(label, color, name=f"cover-{article.pk}.png")
            article.save()

        # Статьи распределены по датам с января 2024 года,
        # чтобы было что фильтровать через created_after и created_before.
        # auto_now_add не даёт задать дату при создании, поэтому меняем её
        # отдельным UPDATE — и последним шагом: save() выше записал бы
        # в базу старую дату из объекта в памяти.
        start = timezone.make_aware(datetime(2024, 1, 10, 10, 0))
        for index, article in enumerate(articles):
            Article.objects.filter(pk=article.pk).update(created_at=start + timedelta(days=index * 35))

        ArticleAttachment.objects.create(
            article=articles[0],
            file=ContentFile("Конспект урока 8: продвинутые возможности DRF.\n".encode(), name="notes.txt"),
            filename="Конспект урока.txt",
        )

        commenters = [users["john"], users["editor"], users["premium"], users["anna"]]
        comments_total = 0
        for index, article in enumerate(a for a in articles if a.published):
            for offset in range(index % 4):
                Comment.objects.create(
                    article=article,
                    author=commenters[(index + offset) % len(commenters)],
                    text=COMMENTS[(index + offset) % len(COMMENTS)],
                )
                comments_total += 1

        self.stdout.write(self.style.SUCCESS("Демо-данные созданы."))
        self.stdout.write(
            f"Статей: {len(PUBLISHED_TITLES)} опубликовано и {len(DRAFT_TITLES)} черновика, "
            f"комментариев: {comments_total}.\n"
        )
        self.stdout.write("Пользователи (логин / пароль — роль):")
        self.stdout.write("  admin   / admin123   — администратор (is_staff), подписка premium")
        self.stdout.write("  john    / secret123  — обычный автор, подписка free")
        self.stdout.write("  editor  / editor123  — группа Editors, видит все черновики, подписка basic")
        self.stdout.write("  anna    / anna12345  — email НЕ подтверждён: не может создавать статьи")
        self.stdout.write("  premium / premium123 — подписка premium: высокий лимит в /api/feed/")
