"""
Настройки демо-проекта к уроку 8 «Django REST Framework: продвинутые возможности».

На прошлом уроке мы сделали CRUD API для одной модели: сериализатор превращает
объекты Django в JSON и обратно, ViewSet собирает обработку всех HTTP-методов
в одном классе, роутер сам создаёт URL-маршруты.

В production API должно быть не только рабочим, но и безопасным, быстрым
и удобным. В этом проекте собраны продвинутые возможности DRF:
    * аутентификация: Session, Token, JWT;
    * права доступа: встроенные и свои permissions;
    * ограничение частоты запросов (throttling);
    * фильтрация, поиск и сортировка;
    * пагинация трёх видов;
    * вложенные сериализаторы;
    * загрузка файлов.

Проект учебный: DEBUG включён, SECRET_KEY по умолчанию небезопасный.
Для настоящего сервера задайте переменные DJANGO_SECRET_KEY и DJANGO_DEBUG=0.
"""

import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-demo-key-only-for-local-lessons-change-me-in-production",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Django REST Framework.
    "rest_framework",
    # Таблица токенов для Token Authentication. После добавления приложения
    # нужно выполнить миграции: python manage.py migrate.
    "rest_framework.authtoken",
    # Чёрный список refresh-токенов JWT. В методичке этого приложения нет.
    # Без него настройка BLACKLIST_AFTER_ROTATION (см. SIMPLE_JWT ниже)
    # молча ничего не делает: ошибки нет, а старый refresh token
    # после обновления продолжает работать.
    "rest_framework_simplejwt.token_blacklist",
    # django-filter: фильтрация через параметры URL (?author=5&published=true).
    "django_filters",
    # Наши приложения.
    "users",
    "blog",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Своя модель пользователя: в методичке «предполагается», что у User есть поля
# email_verified (для HasVerifiedEmail) и subscription_level
# (для SubscriptionRateThrottle). Здесь они есть на самом деле: users/models.py.
AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

# Работа с файлами: upload_to в модели задаёт папку внутри MEDIA_ROOT,
# а MEDIA_URL — адрес, по которому файл отдаётся клиенту.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


REST_FRAMEWORK = {
    # --- Аутентификация: «кто вы?» ---
    # DRF пробует классы по очереди, пока один не опознает пользователя.
    # Если ни один не опознал, request.user будет AnonymousUser.
    #   * JWTAuthentication — самодостаточные токены, популярны в микросервисах.
    #   * TokenAuthentication — случайная строка в заголовке Authorization,
    #     хороший выбор для мобильных приложений и отдельного frontend.
    #   * SessionAuthentication — стандартные сессии Django и cookie, удобно,
    #     когда frontend и backend на одном домене. Для POST, PUT и DELETE
    #     DRF проверяет CSRF-токен.
    # Порядок важен: заголовок WWW-Authenticate берётся из первого класса.
    # Если первым стоит SessionAuthentication, у него нет такого заголовка,
    # и анонимный запрос получит 403 вместо 401 Unauthorized.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    # --- Авторизация: «что вам разрешено?» ---
    # Права по умолчанию: читать могут все, изменять — только вошедшие.
    # Во ViewSet их можно переопределить через permission_classes.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    # --- Throttling: ограничение частоты запросов ---
    # Защищает от DDoS, ботов и делит ресурсы сервера честно между клиентами.
    # AnonRateThrottle считает запросы анонимов по IP-адресу,
    # UserRateThrottle — вошедших пользователей по их id.
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    # Формат лимита: '5/second', '60/minute', '1000/hour' или '10000/day'.
    # В методичке anon — 100/day и user — 1000/day. Здесь лимиты выше:
    # каждый вход по паролю — анонимный запрос, и прогон demo/walkthrough.py
    # тратит пару десятков анонимных запросов. С лимитом 100/day репетиция
    # и показ на уроке исчерпали бы его. Соотношение 1:10 сохранено.
    # burst и sustained — свои «области» (scope) из blog/throttles.py,
    # их значения — как в методичке.
    "DEFAULT_THROTTLE_RATES": {
        "anon": "1000/hour",
        "user": "10000/hour",
        "burst": "10/minute",
        "sustained": "100/hour",
    },
    # --- Фильтрация ---
    # Бэкенд django-filter по умолчанию. ViewSet может задать свой список
    # filter_backends, например добавить SearchFilter и OrderingFilter.
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    # --- Пагинация ---
    # PageNumberPagination работает как страницы книги: ?page=2.
    # Все list-эндпоинты возвращают не больше PAGE_SIZE объектов.
    # Свои классы пагинации — в blog/pagination.py.
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
}

# Счётчики throttling хранятся в кеше Django. По умолчанию это память
# процесса (LocMemCache), поэтому перезапуск runserver обнуляет лимиты.
# На нескольких серверах нужен общий кеш, например Redis.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# --- JWT (djangorestframework-simplejwt) ---
# Токен состоит из трёх частей через точку: заголовок (тип и алгоритм),
# полезная нагрузка (claims — утверждения о пользователе) и подпись.
# Сервер проверяет подпись и не обращается к базе данных.
SIMPLE_JWT = {
    # Access token живёт 60 минут и используется в обычных запросах.
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    # Refresh token живёт 7 дней: по нему клиент получает новый access token.
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    # При обновлении access token выдаётся и новый refresh token.
    "ROTATE_REFRESH_TOKENS": True,
    # Старый refresh token после обновления попадает в чёрный список.
    # Работает, только если подключено приложение
    # rest_framework_simplejwt.token_blacklist (см. INSTALLED_APPS).
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    # Заголовок запроса: Authorization: Bearer <access token>.
    "AUTH_HEADER_TYPES": ("Bearer",),
}
