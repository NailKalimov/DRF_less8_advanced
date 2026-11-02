"""Три вида пагинации DRF.

Когда в базе тысячи записей, отдавать их одним ответом неэффективно,
а иногда и невозможно. Пагинация делит результат на порции.

В проекте каждый вид подключён к своему эндпоинту:
  * CustomPageNumberPagination  — /api/articles/  (?page=2&page_size=25)
  * CustomLimitOffsetPagination — /api/comments/  (?limit=20&offset=40)
  * ArticleCursorPagination     — /api/feed/      (?cursor=...)
"""

from rest_framework.pagination import (
    CursorPagination,
    LimitOffsetPagination,
    PageNumberPagination,
)


class CustomPageNumberPagination(PageNumberPagination):
    """Номера страниц, как в книге, и размер страницы на выбор клиента.

    Ответ содержит метаинформацию:
        count    — сколько всего объектов;
        next     — ссылка на следующую страницу;
        previous — ссылка на предыдущую;
        results  — сами данные.
    """

    page_size = 10
    # Клиент сам задаёт размер страницы: ?page_size=25.
    page_size_query_param = "page_size"
    # Потолок размера страницы: защита от ?page_size=1000000.
    max_page_size = 100
    page_query_param = "page"


class CustomLimitOffsetPagination(LimitOffsetPagination):
    """Сколько пропустить (offset) и сколько вернуть (limit).

    ?limit=20&offset=40 вернёт записи с 41-й по 60-ю.
    Гибче номеров страниц, но менее понятно человеку.
    """

    default_limit = 10
    max_limit = 100
    limit_query_param = "limit"
    offset_query_param = "offset"


class ArticleCursorPagination(CursorPagination):
    """Курсорная пагинация — самая продвинутая.

    Вместо номера страницы клиент передаёт курсор — закодированную строку,
    которая указывает на место в упорядоченной выборке. Пагинация остаётся
    стабильной, даже когда данные меняются: новые статьи не сдвигают
    страницы, записи не повторяются и не теряются. Для очень больших
    наборов данных это единственный подходящий вариант.

    Курсор требует поле сортировки (ordering). Клиент не собирает курсор
    сам, а берёт готовые ссылки next и previous из ответа.
    Поля count в ответе нет.
    """

    page_size = 10
    ordering = "-created_at"
    cursor_query_param = "cursor"
