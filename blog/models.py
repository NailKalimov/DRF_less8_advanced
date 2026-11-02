from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models

from .images import make_thumbnail
from .validators import validate_file_size

IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "webp"]
ATTACHMENT_EXTENSIONS = ["pdf", "docx", "txt"]


class Article(models.Model):
    """Статья блога — основная сущность урока."""

    title = models.CharField("заголовок", max_length=200)
    content = models.TextField("текст")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="articles",
        verbose_name="автор",
    )
    # Обычные пользователи видят только опубликованные статьи,
    # а автор и редакторы — ещё и черновики (см. CanViewUnpublished).
    published = models.BooleanField("опубликована", default=False)
    # upload_to — папка внутри MEDIA_ROOT, куда сохранится файл.
    # FileExtensionValidator ограничивает типы файлов. Это повышает
    # безопасность, но проверяет только расширение. Что внутри действительно
    # картинка, проверяет ImageField с помощью Pillow.
    cover_image = models.ImageField(
        "обложка",
        upload_to="articles/covers/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=IMAGE_EXTENSIONS), validate_file_size],
    )
    # Миниатюра создаётся автоматически в save(), клиент её не присылает.
    cover_thumbnail = models.ImageField(
        "миниатюра обложки",
        upload_to="articles/thumbnails/",
        null=True,
        blank=True,
        editable=False,
    )
    created_at = models.DateTimeField("создана", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "статья"
        verbose_name_plural = "статьи"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """Создаёт миниатюру при сохранении, если загружена новая обложка.

        В методичке миниатюра пересоздаётся при каждом save(), даже если
        поменяли только заголовок. Здесь — только когда обложка новая:
        файл присвоен полю, но ещё не записан в хранилище
        (_committed == False). Так бывает при загрузке через API и в админке.
        """
        if self.cover_image and not self.cover_image._committed:
            if self.cover_thumbnail:
                self.cover_thumbnail.delete(save=False)
            self.cover_thumbnail = make_thumbnail(self.cover_image)
        elif not self.cover_image and self.cover_thumbnail:
            # Обложку убрали — убираем и миниатюру.
            self.cover_thumbnail.delete(save=False)
            self.cover_thumbnail = None
        super().save(*args, **kwargs)


class Comment(models.Model):
    """Комментарий к статье: связь ForeignKey для примеров вложенных сериализаторов."""

    # related_name="comments" даёт обратную связь article.comments
    # (reverse relationship), её используют вложенные сериализаторы.
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="статья",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="автор",
    )
    text = models.TextField("текст")
    created_at = models.DateTimeField("создан", auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "комментарий"
        verbose_name_plural = "комментарии"

    def __str__(self):
        return f"{self.author} → {self.article}"


class ArticleAttachment(models.Model):
    """Файл, прикреплённый к статье: документы PDF, DOCX или TXT."""

    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="статья",
    )
    file = models.FileField(
        "файл",
        upload_to="articles/attachments/",
        validators=[
            FileExtensionValidator(allowed_extensions=ATTACHMENT_EXTENSIONS),
            validate_file_size,
        ],
    )
    filename = models.CharField("имя файла", max_length=255)
    uploaded_at = models.DateTimeField("загружен", auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at", "id"]
        verbose_name = "вложение"
        verbose_name_plural = "вложения"

    def __str__(self):
        return self.filename
