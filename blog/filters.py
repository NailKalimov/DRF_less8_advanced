"""Фильтрация статей через django-filter.

Клиенту редко нужны все объекты сразу. Фильтры позволяют запросить только
нужное, добавив параметры в URL: это быстрее и удобнее.

Простой вариант — список полей во ViewSet:
    filterset_fields = ["author", "published"]
    GET /api/articles/?author=5&published=true

Для сложной фильтрации пишем свой FilterSet, как ниже.
"""

import django_filters
from django.contrib.auth import get_user_model

from .models import Article

User = get_user_model()


class NumberInFilter(django_filters.BaseInFilter, django_filters.NumberFilter):
    """Фильтр по списку чисел через запятую: ?author_in=1,3,5."""


class ArticleFilter(django_filters.FilterSet):
    # CharFilter с lookup_expr="icontains" ищет по частичному совпадению
    # без учёта регистра: ?title=django найдёт «Django Tips» и «Learning Django».
    # SQLite не учитывает регистр только для латиницы, поэтому
    # «джанго» и «Джанго» для него разные строки. PostgreSQL их не различает.
    title = django_filters.CharFilter(lookup_expr="icontains")

    # DateTimeFilter с lookup_expr="gte" (больше или равно) и "lte"
    # (меньше или равно) задают диапазон дат:
    #   ?created_after=2024-01-01&created_before=2024-12-31
    # Дата без времени означает полночь: created_before=2024-12-31 не включит
    # статьи, написанные 31 декабря днём.
    created_after = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    # ModelMultipleChoiceFilter — несколько авторов сразу.
    # Отличие от методички: id передаются повторением параметра,
    #   ?authors=1&authors=3
    # а не через запятую. Запрос ?authors=1,3 вернёт ошибку 400.
    authors = django_filters.ModelMultipleChoiceFilter(
        field_name="author",
        queryset=User.objects.all(),
    )

    # Если нужен именно список через запятую, подойдёт BaseInFilter:
    #   ?author_in=1,3,5
    author_in = NumberInFilter(field_name="author", lookup_expr="in")

    class Meta:
        model = Article
        # Поля с точным совпадением: ?author=5, ?published=true.
        # title объявлен выше явно, поэтому для него работает icontains.
        fields = ["author", "published", "title"]
