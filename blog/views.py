"""ViewSet'ы блога. Здесь сходятся все темы урока.

ArticleViewSet — /api/articles/
    аутентификация, права, throttling, фильтры, поиск, сортировка,
    пагинация по страницам, вложенные сериализаторы, загрузка файлов.
CommentViewSet — /api/comments/
    пагинация limit/offset, Meta.depth.
FeedViewSet — /api/feed/
    курсорная пагинация, лимит по уровню подписки.
"""

from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .filters import ArticleFilter
from .models import Article, Comment
from .pagination import (
    ArticleCursorPagination,
    CustomLimitOffsetPagination,
    CustomPageNumberPagination,
)
from .permissions import CanViewUnpublished, HasVerifiedEmail, IsAuthorOrReadOnly, is_editor
from .serializers import (
    ArticleAttachmentSerializer,
    ArticleCoverSerializer,
    ArticleDetailSerializer,
    ArticleSerializer,
    CommentDepthSerializer,
    CommentWriteSerializer,
)
from .throttles import BurstRateThrottle, SubscriptionRateThrottle, SustainedRateThrottle


class ArticleViewSet(viewsets.ModelViewSet):
    """CRUD статей со всеми продвинутыми возможностями DRF."""

    # --- Права доступа ---
    # Все классы должны вернуть True:
    #   IsAuthenticatedOrReadOnly — читают все, создают только вошедшие;
    #   IsAuthorOrReadOnly        — менять и удалять может только автор;
    #   HasVerifiedEmail          — изменения только с подтверждённым email;
    #   CanViewUnpublished        — черновик видят только автор и редакторы.
    permission_classes = [
        IsAuthenticatedOrReadOnly,
        IsAuthorOrReadOnly,
        HasVerifiedEmail,
        CanViewUnpublished,
    ]

    # --- Throttling ---
    # Для всех действий, кроме create, действует «длинный» лимит.
    # Действие может задать свой: см. publish.
    throttle_classes = [SustainedRateThrottle]

    # --- Фильтрация, поиск и сортировка ---
    # DjangoFilterBackend — фильтры из ArticleFilter: ?author=5&published=true.
    # SearchFilter — поиск по нескольким полям сразу одним параметром ?search=.
    # OrderingFilter — сортировка, которую выбирает клиент: ?ordering=-created_at.
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ArticleFilter
    # ?search=django найдёт «django» в заголовке, тексте или имени автора.
    # По умолчанию поиск идёт по icontains. Префикс у поля меняет тип поиска:
    #   "^title"            — заголовок начинается с запроса;
    #   "=author__username" — точное совпадение;
    #   "@content"          — полнотекстовый поиск (нужна поддержка БД, PostgreSQL);
    #   "$title"            — поиск по регулярному выражению.
    search_fields = ["title", "content", "author__username"]
    # Поля, по которым клиент может сортировать.
    # Минус перед именем — по убыванию: ?ordering=-created_at.
    ordering_fields = ["created_at", "title", "author__username"]
    # Сортировка по умолчанию, если клиент не передал ?ordering=.
    ordering = ["-created_at"]

    # --- Пагинация ---
    # Номера страниц и размер страницы на выбор клиента: ?page=2&page_size=25.
    pagination_class = CustomPageNumberPagination

    # --- Парсеры ---
    # Парсер разбирает тело запроса по заголовку Content-Type:
    #   JSONParser      — обычный JSON;
    #   MultiPartParser — multipart/form-data, нужен для загрузки файлов;
    #   FormParser      — обычные HTML-формы.
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        """Выборка статей с оптимизацией запросов к БД.

        select_related("author") подтягивает автора тем же SQL-запросом (JOIN).
        prefetch_related("comments__author") загружает комментарии и их авторов
        отдельными запросами сразу для всех статей.
        Без этого получилась бы проблема N+1: один запрос на список
        и ещё по запросу на каждую статью.
        """
        queryset = Article.objects.select_related("author")

        # Оптимизация запросов для детального просмотра.
        if self.action == "retrieve":
            queryset = queryset.prefetch_related("comments__author", "attachments")

        # Черновики в списке видят только их авторы, а редакторы видят все.
        # Доступ к одной статье проверяет CanViewUnpublished.
        if self.action == "list":
            user = self.request.user
            if not is_editor(user):
                if user.is_authenticated:
                    queryset = queryset.filter(Q(published=True) | Q(author=user))
                else:
                    queryset = queryset.filter(published=True)

        return queryset

    def get_serializer_class(self):
        """Свой сериализатор для каждого действия.

        Список — лёгкий ArticleSerializer без комментариев,
        одна статья — ArticleDetailSerializer со всеми связанными данными.
        Для загрузки файлов — сериализаторы с одним полем-файлом:
        browsable API покажет по ним форму загрузки.
        """
        if self.action == "retrieve":
            return ArticleDetailSerializer
        if self.action == "upload_cover":
            return ArticleCoverSerializer
        if self.action == "add_attachment":
            return ArticleAttachmentSerializer
        return ArticleSerializer

    def get_throttles(self):
        """Свои throttle-классы для каждого действия.

        Создание статьи — 10 запросов в минуту (burst),
        остальное — 100 в час (sustained).

        Отличие от методички: там для остальных действий возвращается
        [SustainedRateThrottle()]. Тогда throttle_classes из @action
        не работают, и publish тоже получает sustained.
        super().get_throttles() берёт throttle_classes текущего действия.
        """
        if self.action == "create":
            return [BurstRateThrottle()]
        return super().get_throttles()

    def perform_create(self, serializer):
        """Автор статьи — текущий пользователь.

        Если пользователь не вошёл, request.user — это AnonymousUser.
        Сюда он не попадёт: IsAuthenticatedOrReadOnly вернёт 401 раньше.
        """
        serializer.save(author=self.request.user)

    @action(detail=True, methods=["post"], throttle_classes=[BurstRateThrottle])
    def publish(self, request, pk=None):
        """Публикация статьи: POST /api/articles/<id>/publish/.

        get_object() проверяет права на объект: опубликовать может только автор.
        throttle_classes в @action задаёт этому действию свой лимит.
        """
        article = self.get_object()
        article.published = True
        article.save(update_fields=["published"])
        return Response({"status": "article published"})

    @action(detail=False, methods=["get"], permission_classes=[IsAdminUser])
    def pending_review(self, request):
        """Статьи на проверке: GET /api/articles/pending_review/.

        permission_classes в @action заменяют права ViewSet для этого действия:
        список доступен только администраторам (is_staff=True), хотя
        сам ViewSet читать может кто угодно.
        """
        pending = Article.objects.filter(published=False).select_related("author")
        page = self.paginate_queryset(pending)
        serializer = ArticleSerializer(page, many=True, context=self.get_serializer_context())
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def upload_cover(self, request, pk=None):
        """Загрузка обложки: POST /api/articles/<id>/upload_cover/.

        Тело — multipart/form-data с полем cover_image.
        Старая обложка удаляется, миниатюра создаётся заново в Article.save().
        """
        article = self.get_object()

        serializer = ArticleCoverSerializer(article, data=request.data)
        serializer.is_valid(raise_exception=True)

        # Удаляем старое изображение, если оно есть.
        if article.cover_image:
            article.cover_image.delete(save=False)

        serializer.save()
        return Response(ArticleSerializer(article, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def add_attachment(self, request, pk=None):
        """Прикрепить файл к статье: POST /api/articles/<id>/add_attachment/.

        Тело — multipart/form-data: поле file и необязательное поле filename.

        Отличие от методички: там вложение создаётся через
        ArticleAttachment.objects.create(...), а ORM не запускает
        валидаторы полей. Тогда FileExtensionValidator и validate_file_size
        молча пропускают любой файл. Сериализатор их запускает.
        """
        article = self.get_object()

        serializer = ArticleAttachmentSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        serializer.save(article=article)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CommentViewSet(viewsets.ModelViewSet):
    """Комментарии: пагинация limit/offset и Meta.depth.

    GET  /api/comments/?limit=5&offset=10
    GET  /api/comments/?article=3
    POST /api/comments/  {"article": 3, "text": "..."}
    """

    permission_classes = [IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
    pagination_class = CustomLimitOffsetPagination
    # Простая фильтрация списком полей, без своего FilterSet.
    filterset_fields = ["article", "author"]

    def get_queryset(self):
        # Комментарии есть только у опубликованных статей.
        return Comment.objects.filter(article__published=True).select_related("author", "article")

    def get_serializer_class(self):
        # Чтение — с раскрытой статьёй (depth=1), запись — по id статьи.
        if self.action in ("list", "retrieve"):
            return CommentDepthSerializer
        return CommentWriteSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class FeedViewSet(viewsets.ReadOnlyModelViewSet):
    """Лента опубликованных статей: GET /api/feed/.

    * Курсорная пагинация: переходы только по ссылкам next и previous.
    * Лимит зависит от подписки: аноним 10, free 20, basic 60,
      premium 600 запросов в минуту.
    """

    queryset = Article.objects.filter(published=True).select_related("author")
    serializer_class = ArticleSerializer
    permission_classes = [AllowAny]
    pagination_class = ArticleCursorPagination
    # Задаём список явно: глобальные AnonRateThrottle и UserRateThrottle
    # здесь не действуют.
    throttle_classes = [SubscriptionRateThrottle]
    # Порядок задаёт курсорная пагинация. OrderingFilter тут не нужен.
    filter_backends = []
