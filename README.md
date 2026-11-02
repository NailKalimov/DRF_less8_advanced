# Django REST Framework: продвинутые возможности

Демо-проект к уроку 8 курса Python8. API блога, на котором видна каждая тема урока:

| Тема урока | Где в коде | Где посмотреть |
|---|---|---|
| Аутентификация: Session, Token, JWT | `config/settings.py`, `users/views.py`, `users/serializers.py` | `/api/auth/...`, `/api-auth/login/` |
| Права: встроенные и свои | `blog/permissions.py`, `ArticleViewSet` в `blog/views.py` | `/api/articles/` |
| Throttling | `blog/throttles.py`, `get_throttles()` в `blog/views.py` | `/api/articles/`, `/api/feed/` |
| Фильтрация, поиск, сортировка | `blog/filters.py`, `ArticleViewSet` | `/api/articles/?search=...` |
| Пагинация трёх видов | `blog/pagination.py` | `/api/articles/`, `/api/comments/`, `/api/feed/` |
| Вложенные сериализаторы | `blog/serializers.py`, `get_queryset()` | `/api/articles/<id>/`, `/api/comments/` |
| Файлы: обложка, миниатюра, вложения | `blog/models.py`, `blog/images.py`, `blog/validators.py` | `/api/articles/<id>/upload_cover/`, `.../add_attachment/` |

Комментарии в коде пересказывают методичку: что делает каждый механизм и зачем он нужен.

## Запуск

Нужен Python 3.11 или новее.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS и Linux:
source .venv/bin/activate

pip install -r requirements-dev.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Откройте http://127.0.0.1:8000/api/ — это browsable API DRF: по ссылкам можно ходить прямо в браузере.

`seed_demo` создаёт 5 пользователей, 25 опубликованных статей, 3 черновика, комментарии, три обложки и одно вложение. Команду можно запускать повторно: статьи пересоздаются, пароли сбрасываются.

### Пользователи

| Логин | Пароль | Роль |
|---|---|---|
| `admin` | `admin123` | администратор (`is_staff`), доступ к `pending_review`, подписка premium |
| `john` | `secret123` | обычный автор, подписка free |
| `editor` | `editor123` | группа `Editors`: видит все черновики, подписка basic |
| `anna` | `anna12345` | email не подтверждён: не может создавать статьи |
| `premium` | `premium123` | подписка premium: высокий лимит в ленте |

Пароли простые: проект только для локальной демонстрации.

## Как показывать

Есть три способа, их можно совмещать.

**1. Скрипт по разделам методички.** Во втором терминале при запущенном сервере:

```bash
python demo/walkthrough.py --pause          # все разделы, пауза после каждого
python demo/walkthrough.py --only files     # один раздел
```

Разделы: `auth`, `permissions`, `filters`, `pagination`, `nested`, `files`, `throttling`. Скрипт печатает каждый запрос, код ответа и главное из тела ответа.

**2. Запросы из IDE.** `demo/api.http` открывается в PyCharm (HTTP Client) и в VS Code (расширение REST Client). Запросы сгруппированы по разделам урока, у каждого есть кнопка запуска.

**3. Браузер.** Войдите через «Log in» в правом верхнем углу browsable API: запросы пойдут через SessionAuthentication. На странице `/api/articles/<id>/upload_cover/` есть форма загрузки файла.

### Сценарий урока

1. **Аутентификация.** `GET /api/auth/me/` без входа даёт 401. Затем вход тремя способами: Token (`/api/auth/login/`), JWT (`/api/auth/token/`), сессия (браузер). Поле `authenticated_via` в ответе `/api/auth/me/` показывает, какой класс опознал пользователя. Payload JWT можно раскодировать: в нём видны свои claims.
2. **Права.** Аноним читает, но не пишет. anna получает 403 из-за неподтверждённого email. editor не может править статью john. Чужой черновик: аноним получает 401, другой пользователь — 403, редактор — 200. `pending_review` открыт только admin.
3. **Фильтрация.** `?author=`, `?title=`, `?created_after=`, `?authors=1&authors=3`, `?search=`, `?ordering=` и всё вместе.
4. **Пагинация.** `page` и `page_size` у статей, `limit` и `offset` у комментариев, `cursor` в ленте.
5. **Вложенные сериализаторы.** Список статей лёгкий, одна статья — с комментариями. `Meta.depth` в комментариях.
6. **Файлы.** Загрузка обложки, автоматическая миниатюра, вложения, отказ для `.exe` и для файла больше 5 МБ.
7. **Throttling.** Показывайте последним: после него лимиты исчерпаны. 11-е создание статьи за минуту даёт 429 и заголовок `Retry-After`. В ленте лимит зависит от подписки.

Счётчики throttling хранятся в памяти сервера. Перезапуск `runserver` их обнуляет.

## Эндпоинты

| Метод и путь | Что делает |
|---|---|
| `POST /api/auth/obtain-token/` | DRF-токен, готовое представление `obtain_auth_token` |
| `POST /api/auth/login/` | DRF-токен и данные пользователя (`custom_login`) |
| `POST /api/auth/logout/` | удалить DRF-токен |
| `POST /api/auth/token/` | пара JWT со своими claims |
| `POST /api/auth/token/refresh/` | новый access token (и новый refresh) |
| `POST /api/auth/token/blacklist/` | refresh token в чёрный список |
| `GET /api/auth/me/` | текущий пользователь и способ входа |
| `GET, POST /api/articles/` | список и создание статей |
| `GET, PATCH, PUT, DELETE /api/articles/<id>/` | одна статья |
| `POST /api/articles/<id>/publish/` | опубликовать |
| `POST /api/articles/<id>/upload_cover/` | загрузить обложку |
| `POST /api/articles/<id>/add_attachment/` | прикрепить файл |
| `GET /api/articles/pending_review/` | неопубликованные статьи, только admin |
| `GET, POST /api/comments/` | комментарии |
| `GET /api/feed/` | лента с курсорной пагинацией |

## Тесты

```bash
pytest
```

Тесты разбиты по темам урока: `tests/test_auth.py`, `test_permissions.py`, `test_throttling.py`, `test_filters.py`, `test_pagination.py`, `test_nested.py`, `test_files.py`. Их тоже можно разбирать на уроке: каждый тест — короткий пример запроса и ожидаемого ответа.

## Где код отличается от методички

Код методички в нескольких местах работает не так, как описано в тексте. Здесь эти места исправлены, а каждое отличие подтверждено тестом.

| Методичка | Что происходит на самом деле | Как сделано здесь | Тест |
|---|---|---|---|
| `SubscriptionRateThrottle` пересчитывает лимит в `get_rate()` | DRF вызывает `get_rate()` один раз в `__init__`, когда запроса ещё нет. Лимит становится `None`, и throttle не ограничивает никого | лимит пересчитывается в `allow_request()`, у класса своя область `scope = "subscription"` | `test_lesson_subscription_throttle_never_limits` |
| `get_throttles()` возвращает `[SustainedRateThrottle()]` для всех действий, кроме create | `throttle_classes` из `@action(...)` перестают работать: `publish` получает sustained вместо burst | `return super().get_throttles()` | `test_publish_action_uses_its_own_throttle` |
| `?authors=1,3,5` для `ModelMultipleChoiceFilter` | такой запрос возвращает 400. Этот фильтр ждёт `?authors=1&authors=3` | оставлен `authors`, добавлен `author_in` на `BaseInFilter` для списка через запятую | `test_authors_multiple_choice_rejects_comma_list` |
| `BLACKLIST_AFTER_ROTATION: True` без приложения `token_blacklist` | ошибки нет, но старый refresh token продолжает работать | `rest_framework_simplejwt.token_blacklist` в `INSTALLED_APPS` | `test_jwt_refresh_rotates_and_blacklists_old_token` |
| `ArticleAttachment.objects.create(file=...)` в `add_attachment` | ORM не запускает валидаторы полей: `.exe` и файл любого размера сохраняются | загрузка через сериализатор | `test_orm_create_skips_model_validators`, `test_add_attachment_rejects_extension` |
| `article.cover_image = request.FILES[...]` в `upload_cover` | то же: ни расширение, ни размер, ни содержимое не проверяются | `ArticleCoverSerializer` | `test_upload_cover_rejects_bad_files` |
| Миниатюра: `img.save(..., format="JPEG")` | PNG с прозрачностью падает: `cannot write mode RGBA as JPEG`. Миниатюра пересоздаётся при каждом `save()` | `convert("RGB")`, миниатюра только для новой обложки | `test_upload_cover_creates_thumbnail` |
| `IsAuthenticated` даёт 401 | если первым в `DEFAULT_AUTHENTICATION_CLASSES` стоит `SessionAuthentication`, будет 403 | первым стоит `JWTAuthentication` | `test_session_authentication_first_turns_401_into_403` |
| `depth = 1` как способ вложенности | если связь с пользователем не объявлена явно, в ответ попадают хеш пароля, email и `is_superuser` | автор объявлен явно, `UserSerializer` без email | `test_depth_without_explicit_author_leaks_password` |

Мелкие отличия:

* лимиты `anon` и `user` подняты с `100/day` и `1000/day` до `1000/hour` и `10000/hour`, а лимиты подписки считаются в минуту, чтобы их было видно на уроке;
* в методичке есть `status='pending'` и `published`. Здесь одно поле `published`, а `pending_review` показывает неопубликованные статьи;
* `/api/auth/me/`, `/api/auth/logout/` и `/api/auth/token/blacklist/` добавлены для наглядности, в методичке их нет.

## Структура

```
config/          настройки и корневые URL
users/           модель пользователя, вход, токены, /api/auth/me/
blog/
  models.py        Article, Comment, ArticleAttachment
  serializers.py   вложенные сериализаторы и файлы
  views.py         ArticleViewSet, CommentViewSet, FeedViewSet
  permissions.py   IsAuthorOrReadOnly, CanViewUnpublished, HasVerifiedEmail
  throttles.py     Burst, Sustained, SubscriptionRateThrottle
  filters.py       ArticleFilter
  pagination.py    PageNumber, LimitOffset, Cursor
  images.py        миниатюры через Pillow
  validators.py    проверка размера файла
  management/commands/seed_demo.py
demo/            walkthrough.py, api.http и файлы для загрузки
tests/           тесты по темам урока
```
