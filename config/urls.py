"""Корневые маршруты проекта."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # Вход, выход, токены и профиль: users/urls.py.
    path("api/auth/", include("users.urls")),
    # Статьи, комментарии и лента: роутер в blog/urls.py.
    path("api/", include("blog.urls")),
    # Вход и выход в browsable API (страницы DRF в браузере).
    # После входа запросы идут через SessionAuthentication.
    path("api-auth/", include("rest_framework.urls")),
]

if settings.DEBUG:
    # В разработке Django сам отдаёт загруженные файлы из MEDIA_ROOT.
    # На сервере это делает веб-сервер (nginx) или облачное хранилище.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
