"""Сериализаторы блога: вложенные данные и файлы.

Модели связаны через ForeignKey. Вложенные сериализаторы (nested serializers)
кладут связанные объекты прямо в JSON, и клиенту не нужны лишние запросы.
"""

from rest_framework import serializers

from users.serializers import UserSerializer

from .models import Article, ArticleAttachment, Comment


def absolute_file_url(serializer, file_field):
    """Полный URL файла с протоколом и доменом, например http://127.0.0.1:8000/media/....

    build_absolute_uri берёт протокол и домен из запроса. Запрос попадает
    в сериализатор через context: ViewSet передаёт его сам, а при ручном
    создании сериализатора context={"request": request} нужно передать явно.
    В методичке нет проверки на отсутствие request. Здесь без него
    возвращается относительный путь вместо ошибки.
    """
    if not file_field:
        return None
    request = serializer.context.get("request")
    if request is None:
        return file_field.url
    return request.build_absolute_uri(file_field.url)


class CommentSerializer(serializers.ModelSerializer):
    """Комментарий с вложенным автором: используется внутри статьи."""

    author = UserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "text", "author", "created_at"]


class CommentWriteSerializer(CommentSerializer):
    """Создание и изменение комментария: POST/PATCH /api/comments/.

    Статью клиент указывает по id. Автора не указывает: его ставит
    CommentViewSet.perform_create из request.user.
    """

    article = serializers.PrimaryKeyRelatedField(queryset=Article.objects.filter(published=True))

    class Meta(CommentSerializer.Meta):
        fields = ["id", "article", "text", "author", "created_at"]

    def validate_article(self, article):
        if self.instance is not None and article != self.instance.article:
            raise serializers.ValidationError("Нельзя перенести комментарий в другую статью.")
        return article


class CommentDepthSerializer(serializers.ModelSerializer):
    """Пример Meta.depth: связанная статья раскрывается автоматически.

    depth = 1 сам строит вложенные сериализаторы для всех ForeignKey
    и OneToOne полей на один уровень вглубь. Это быстро, но без контроля:
    раскрываются все поля связанной модели.

    Поэтому автор объявлен явно. С одним depth DRF раскрыл бы пользователя
    целиком: с хешем пароля, email и флагами is_superuser и is_staff.
    Это проверяет тест tests/test_nested.py::test_depth_without_explicit_author_leaks_password.
    Вывод методички: для полного контроля вложенные сериализаторы лучше
    объявлять явно.

    Глубокая вложенность раздувает JSON и замедляет ответ.
    """

    author = UserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "article", "text", "author", "created_at"]
        depth = 1  # Автоматическая вложенность до 1 уровня.


class ArticleAttachmentSerializer(serializers.ModelSerializer):
    """Вложение к статье: загрузка файла и ссылка на него.

    SerializerMethodField — вычисляемое поле только для чтения: значение
    возвращает метод get_<имя поля>.
    """

    file_url = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    # Если клиент не прислал имя, возьмём имя загруженного файла.
    filename = serializers.CharField(max_length=255, required=False)

    class Meta:
        model = ArticleAttachment
        fields = ["id", "filename", "file", "file_url", "file_size", "uploaded_at"]
        read_only_fields = ["uploaded_at"]

    def validate(self, attrs):
        if "file" in attrs and not attrs.get("filename"):
            attrs["filename"] = attrs["file"].name
        return attrs

    def get_file_url(self, obj):
        return absolute_file_url(self, obj.file)

    def get_file_size(self, obj):
        """Размер файла в байтах. None, если файла нет на диске."""
        if not obj.file:
            return 0
        try:
            return obj.file.size
        except OSError:
            return None


class ArticleSerializer(serializers.ModelSerializer):
    """Статья для списка, создания и изменения.

    author = UserSerializer(read_only=True):
      * в ответе вместо "author": 5 будет объект с id, username и именем;
      * read_only=True важен: клиент не должен создавать или менять
        пользователя через статью. Автором становится текущий пользователь,
        его ставит ArticleViewSet.perform_create.
    """

    author = UserSerializer(read_only=True)
    cover_image_url = serializers.SerializerMethodField()
    cover_thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = [
            "id",
            "title",
            "content",
            "author",
            "published",
            "cover_image",
            "cover_image_url",
            "cover_thumbnail_url",
            "created_at",
        ]
        # published меняется только через действие publish,
        # created_at выставляется автоматически.
        read_only_fields = ["published", "created_at"]
        # Обложку клиент присылает файлом, а получает ссылками *_url.
        extra_kwargs = {"cover_image": {"write_only": True}}

    def get_cover_image_url(self, obj):
        return absolute_file_url(self, obj.cover_image)

    def get_cover_thumbnail_url(self, obj):
        return absolute_file_url(self, obj.cover_thumbnail)


class ArticleDetailSerializer(ArticleSerializer):
    """Статья со всеми связанными данными: GET /api/articles/<id>/.

    В списке статей комментарии не нужны, и ArticleSerializer остаётся лёгким.
    Детальный ответ добавляет:
      * comments — список комментариев через обратную связь article.comments.
        many=True означает список объектов, а не один объект;
      * comments_count — source="comments.count" вызывает метод count()
        у related manager;
      * attachments — прикреплённые файлы.
    """

    comments = CommentSerializer(many=True, read_only=True)
    comments_count = serializers.IntegerField(source="comments.count", read_only=True)
    attachments = ArticleAttachmentSerializer(many=True, read_only=True)

    class Meta(ArticleSerializer.Meta):
        fields = ArticleSerializer.Meta.fields + ["comments_count", "comments", "attachments"]


class ArticleCoverSerializer(serializers.ModelSerializer):
    """Загрузка обложки: POST /api/articles/<id>/upload_cover/.

    Отличие от методички: там файл присваивается модели напрямую
    (article.cover_image = request.FILES["cover_image"]). Валидаторы модели
    при этом не запускаются: Django вызывает их только в формах, в full_clean()
    и, через DRF, в ModelSerializer. Тогда можно загрузить «обложку»
    любого размера и с любым содержимым. Сериализатор проверяет расширение,
    размер и то, что файл действительно картинка.
    """

    class Meta:
        model = Article
        fields = ["cover_image"]
        extra_kwargs = {"cover_image": {"required": True, "allow_null": False}}
