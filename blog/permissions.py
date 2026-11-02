"""Свои классы разрешений (permissions).

Встроенные разрешения покрывают простые случаи:
  * IsAuthenticated — только вошедшие пользователи, аноним получит 401;
  * IsAuthenticatedOrReadOnly — читать могут все, изменять только вошедшие;
  * IsAdminUser — только администраторы (is_staff=True).

Для своей бизнес-логики наследуемся от BasePermission и реализуем
один или оба метода:
  * has_permission(request, view) — проверка на уровне всего представления,
    вызывается для каждого запроса;
  * has_object_permission(request, view, obj) — проверка доступа
    к конкретному объекту, вызывается при обращении к одному объекту,
    например /api/articles/5/ (точнее, внутри get_object()).

Если в permission_classes несколько классов, все должны вернуть True.
Хотя бы один False — и доступ запрещён.
"""

from rest_framework import permissions

EDITORS_GROUP = "Editors"


def is_editor(user) -> bool:
    """Пользователь входит в группу редакторов."""
    return user.is_authenticated and user.groups.filter(name=EDITORS_GROUP).exists()


class IsAuthorOrReadOnly(permissions.BasePermission):
    """Редактировать и удалять объект может только его автор."""

    def has_object_permission(self, request, view, obj):
        # Разрешения на чтение доступны всем.
        # SAFE_METHODS — это GET, HEAD и OPTIONS: они не меняют данные.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Разрешения на запись только для автора.
        return obj.author == request.user


class CanViewUnpublished(permissions.BasePermission):
    """Неопубликованную статью видят только её автор и редакторы.

    Это проверка на уровне объекта: она срабатывает на /api/articles/<id>/.
    Список статей фильтруется отдельно, в ArticleViewSet.get_queryset().

    Если проверка вернула False, DRF отвечает:
      * 401 — анониму: «сначала войдите»;
      * 403 — вошедшему пользователю без прав.
    На уроке так нагляднее видна работа has_object_permission. В боевом API
    чужой черновик часто отдают как 404, чтобы клиент не узнал даже
    о его существовании.
    """

    message = "Статья ещё не опубликована."

    def has_object_permission(self, request, view, obj):
        # Если статья опубликована, все могут её видеть.
        if obj.published:
            return True

        # Для неопубликованных проверяем права.
        if request.user.is_authenticated:
            # Автор может видеть свою неопубликованную статью.
            if obj.author == request.user:
                return True
            # Редакторы могут видеть все неопубликованные статьи.
            if is_editor(request.user):
                return True

        return False


class HasVerifiedEmail(permissions.BasePermission):
    """Изменять данные могут только пользователи с подтверждённым email.

    Это проверка на уровне представления (has_permission): она срабатывает
    ещё до поиска объекта, например при создании статьи.
    """

    # Атрибут message — своё сообщение об ошибке для клиента при отказе.
    message = "Вы должны подтвердить email для выполнения этого действия."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        if not request.user.is_authenticated:
            return False

        # Поле email_verified есть в нашей модели users.User.
        return getattr(request.user, "email_verified", False)
