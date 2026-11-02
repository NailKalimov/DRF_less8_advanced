"""Демонстрация урока 8 на работающем сервере.

Скрипт по порядку проходит разделы методички, отправляет запросы через
requests и печатает запрос, код ответа и главное из тела ответа.

Подготовка (в отдельном терминале):
    python manage.py migrate
    python manage.py seed_demo
    python manage.py runserver

Запуск:
    python demo/walkthrough.py                 # все разделы подряд
    python demo/walkthrough.py --pause         # пауза (Enter) после каждого раздела
    python demo/walkthrough.py --only files    # один раздел

Разделы: auth, permissions, filters, pagination, nested, files, throttling.
Throttling идёт последним: он исчерпывает лимиты. Счётчики живут в памяти
сервера и сбрасываются перезапуском runserver.
"""

import argparse
import base64
import functools
import json
import sys
from io import BytesIO

import requests

BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 10

# Пользователи из команды seed_demo.
USERS = {
    "admin": "admin123",
    "john": "secret123",
    "editor": "editor123",
    "anna": "anna12345",
    "premium": "premium123",
}


# --------------------------------------------------------------------------- вывод


def title(text):
    print(f"\n{'=' * 78}\n{text}\n{'=' * 78}")


def step(text):
    print(f"\n--- {text}")


def short(data, limit=600):
    text = json.dumps(data, ensure_ascii=False, indent=2)
    return text if len(text) <= limit else text[:limit] + "\n  ... (обрезано)"


def show(response, *, body=True, extract=None):
    """Печатает запрос и ответ. extract — функция, выбирающая главное из JSON."""
    request = response.request
    print(f"{request.method} {request.url}")
    print(f"<- {response.status_code} {response.reason}")
    for header in ("WWW-Authenticate", "Retry-After"):
        if header in response.headers:
            print(f"   {header}: {response.headers[header]}")
    if not body or not response.content:
        return response
    try:
        data = response.json()
    except ValueError:
        print(response.text[:300])
        return response
    print(short(extract(data) if extract else data))
    return response


class StepFailed(Exception):
    """Сервер ответил не так, как нужно для продолжения раздела."""


def expect(response, status_code):
    """Проверяет код ответа на шаге, от которого зависят следующие шаги."""
    if response.status_code != status_code:
        show(response)
        hint = " Лимит запросов: подождите минуту или перезапустите runserver." if response.status_code == 429 else ""
        raise StepFailed(f"ожидали {status_code}, получили {response.status_code}.{hint}")
    return response


def titles(data):
    """Из ответа со списком статей оставляет счётчик, ссылки и заголовки."""
    result = {key: data[key] for key in ("count", "next", "previous") if key in data}
    result["results"] = [f"#{a['id']} {a['title']} — {a['author']['username']}" for a in data["results"]]
    return result


# --------------------------------------------------------------------------- клиенты


def api(path):
    return f"{BASE_URL}{path}"


# Входим один раз на пользователя: каждый вход — анонимный запрос,
# и он тратит глобальный лимит anon.
@functools.cache
def token_session(username):
    """Клиент с DRF-токеном: Authorization: Token <ключ>."""
    response = requests.post(
        api("/api/auth/login/"), json={"username": username, "password": USERS[username]}, timeout=TIMEOUT
    )
    expect(response, 200)
    session = requests.Session()
    session.headers["Authorization"] = f"Token {response.json()['token']}"
    return session


@functools.cache
def jwt_session(username):
    """Клиент с JWT: Authorization: Bearer <access>."""
    response = requests.post(
        api("/api/auth/token/"), json={"username": username, "password": USERS[username]}, timeout=TIMEOUT
    )
    expect(response, 200)
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {response.json()['access']}"
    return session


def decode_jwt_payload(token):
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def demo_png(size=(1200, 800)):
    """PNG с прозрачностью, нарисованный в памяти."""
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", size, (99, 102, 241, 255))
    ImageDraw.Draw(image).ellipse((200, 100, 1000, 700), fill=(255, 255, 255, 120))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


# --------------------------------------------------------------------------- разделы


def section_auth():
    title("1. Аутентификация: «кто вы?» — Session, Token, JWT")

    step("Аноним запрашивает профиль: IsAuthenticated вернёт 401 Unauthorized")
    show(requests.get(api("/api/auth/me/"), timeout=TIMEOUT))

    step("Token Authentication: готовый obtain_auth_token возвращает только токен")
    response = show(
        requests.post(api("/api/auth/obtain-token/"), json={"username": "john", "password": "secret123"}, timeout=TIMEOUT)
    )
    token = response.json()["token"]

    step("Токен передаём в заголовке Authorization: Token <ключ>")
    show(requests.get(api("/api/auth/me/"), headers={"Authorization": f"Token {token}"}, timeout=TIMEOUT))

    step("Своё представление custom_login: токен и данные пользователя")
    show(requests.post(api("/api/auth/login/"), json={"username": "john", "password": "secret123"}, timeout=TIMEOUT))

    step("Неверный пароль: 400 и сообщение об ошибке")
    show(requests.post(api("/api/auth/login/"), json={"username": "john", "password": "wrong"}, timeout=TIMEOUT))

    step("JWT: пара токенов access и refresh")
    pair = show(
        requests.post(api("/api/auth/token/"), json={"username": "john", "password": "secret123"}, timeout=TIMEOUT),
        extract=lambda d: {k: v[:40] + "..." for k, v in d.items()},
    ).json()

    step("Payload access-токена — это base64, а не шифрование. В нём наши claims")
    print(short(decode_jwt_payload(pair["access"])))

    step("Access token передаём в заголовке Authorization: Bearer <access>")
    show(requests.get(api("/api/auth/me/"), headers={"Authorization": f"Bearer {pair['access']}"}, timeout=TIMEOUT))

    step("Refresh: новый access и, раз ROTATE_REFRESH_TOKENS=True, новый refresh")
    show(
        requests.post(api("/api/auth/token/refresh/"), json={"refresh": pair["refresh"]}, timeout=TIMEOUT),
        extract=lambda d: {k: v[:40] + "..." for k, v in d.items()},
    )

    step("Старый refresh уже в чёрном списке (BLACKLIST_AFTER_ROTATION=True): 401")
    show(requests.post(api("/api/auth/token/refresh/"), json={"refresh": pair["refresh"]}, timeout=TIMEOUT))

    step("Session Authentication: вход через форму /api-auth/login/, cookie sessionid")
    browser = requests.Session()
    browser.get(api("/api-auth/login/"), timeout=TIMEOUT)
    csrf = browser.cookies["csrftoken"]
    browser.post(
        api("/api-auth/login/"),
        data={"username": "john", "password": "secret123", "csrfmiddlewaretoken": csrf, "next": "/api/auth/me/"},
        headers={"Referer": api("/api-auth/login/")},
        timeout=TIMEOUT,
    )
    show(browser.get(api("/api/auth/me/"), timeout=TIMEOUT))

    step("С сессией POST без CSRF-токена запрещён: 403")
    show(browser.post(api("/api/articles/"), json={"title": "t", "content": "c"}, timeout=TIMEOUT))


def section_permissions():
    title("2. Права доступа: «что вам разрешено?»")
    john = token_session("john")

    step("Аноним создаёт статью: IsAuthenticatedOrReadOnly — 401")
    show(requests.post(api("/api/articles/"), json={"title": "t", "content": "c"}, timeout=TIMEOUT))

    step("anna без подтверждённого email: HasVerifiedEmail — 403 со своим message")
    show(token_session("anna").post(api("/api/articles/"), json={"title": "t", "content": "c"}, timeout=TIMEOUT))

    step("john создаёт черновик. Автора ставит perform_create, published только для чтения")
    response = john.post(
        api("/api/articles/"),
        json={"title": "Демо: черновик Джона", "content": "Текст", "published": True},
        timeout=TIMEOUT,
    )
    draft = show(expect(response, 201)).json()
    url = api(f"/api/articles/{draft['id']}/")

    step("editor правит чужую статью: IsAuthorOrReadOnly — 403")
    editor = token_session("editor")
    show(editor.patch(url, json={"title": "Взлом"}, timeout=TIMEOUT))

    step("Чужой черновик: аноним — 401, другой пользователь — 403 (CanViewUnpublished)")
    show(requests.get(url, timeout=TIMEOUT), body=False)
    show(token_session("premium").get(url, timeout=TIMEOUT))

    step("Редактор (группа Editors) видит черновик: 200")
    show(editor.get(url, timeout=TIMEOUT), extract=lambda d: {"id": d["id"], "title": d["title"], "published": d["published"]})

    step("pending_review только для администратора: john — 403, admin — 200")
    show(john.get(api("/api/articles/pending_review/"), timeout=TIMEOUT))
    show(token_session("admin").get(api("/api/articles/pending_review/"), timeout=TIMEOUT), extract=titles)

    step("Автор публикует статью действием publish")
    show(john.post(f"{url}publish/", timeout=TIMEOUT))

    step("Автор удаляет демо-статью")
    show(john.delete(url, timeout=TIMEOUT))


def section_filters():
    title("3. Фильтрация, поиск и сортировка")
    john_id = token_session("john").get(api("/api/auth/me/"), timeout=TIMEOUT).json()["id"]
    editor_id = token_session("editor").get(api("/api/auth/me/"), timeout=TIMEOUT).json()["id"]

    examples = [
        ("filterset: статьи автора john", {"author": john_id}),
        ("CharFilter icontains: в заголовке есть «django»", {"title": "django"}),
        ("DateTimeFilter: диапазон дат", {"created_after": "2024-06-01", "created_before": "2024-12-31"}),
        ("ModelMultipleChoiceFilter: несколько авторов повтором параметра", [("authors", john_id), ("authors", editor_id)]),
        ("BaseInFilter: несколько авторов через запятую", {"author_in": f"{john_id},{editor_id}"}),
        ("SearchFilter: «python» в заголовке, тексте или имени автора", {"search": "python"}),
        ("OrderingFilter: по заголовку", {"ordering": "title", "page_size": 5}),
        ("OrderingFilter: по автору, затем по заголовку", {"ordering": "author__username,title", "page_size": 5}),
        ("Всё вместе: поиск, фильтр и сортировка", {"search": "django", "published": "true", "ordering": "-created_at"}),
    ]
    for text, params in examples:
        step(text)
        show(requests.get(api("/api/articles/"), params=params, timeout=TIMEOUT), extract=titles)

    step("Ошибка из методички: ?authors=1,3 для ModelMultipleChoiceFilter — 400")
    show(requests.get(api(f"/api/articles/?authors={john_id},{editor_id}"), timeout=TIMEOUT))


def section_pagination():
    title("4. Пагинация: номера страниц, limit/offset, курсор")

    step("PageNumberPagination: первая страница, 10 статей, есть count и next")
    show(requests.get(api("/api/articles/"), timeout=TIMEOUT), extract=titles)

    step("Вторая страница по 5 статей: ?page=2&page_size=5")
    show(requests.get(api("/api/articles/"), params={"page": 2, "page_size": 5}, timeout=TIMEOUT), extract=titles)

    step("max_page_size=100: просим 1000, получаем столько, сколько есть, но не больше 100")
    show(
        requests.get(api("/api/articles/"), params={"page_size": 1000}, timeout=TIMEOUT),
        extract=lambda d: {"count": d["count"], "returned": len(d["results"])},
    )

    step("LimitOffsetPagination на комментариях: ?limit=3&offset=5")
    show(
        requests.get(api("/api/comments/"), params={"limit": 3, "offset": 5}, timeout=TIMEOUT),
        extract=lambda d: {
            "count": d["count"],
            "next": d["next"],
            "results": [f"#{c['id']} {c['text']}" for c in d["results"]],
        },
    )

    step("CursorPagination в ленте: count нет, переход только по ссылке next")
    premium = jwt_session("premium")  # premium — чтобы не тратить лимит анонима на ленту
    page = show(premium.get(api("/api/feed/"), timeout=TIMEOUT), extract=titles).json()
    step("Идём по ссылке next из ответа")
    show(premium.get(page["next"], timeout=TIMEOUT), extract=titles)


def section_nested():
    title("5. Вложенные сериализаторы")

    step("Список: лёгкий ArticleSerializer, автор вложен объектом, комментариев нет")
    data = show(
        requests.get(api("/api/articles/"), params={"page_size": 1}, timeout=TIMEOUT),
        extract=lambda d: d["results"][0],
    ).json()
    article_id = data["results"][0]["id"]

    step("Одна статья: ArticleDetailSerializer с comments, comments_count и attachments")
    commented = requests.get(api("/api/comments/"), params={"limit": 1}, timeout=TIMEOUT).json()["results"]
    if commented:
        article_id = commented[0]["article"]["id"]
    show(requests.get(api(f"/api/articles/{article_id}/"), timeout=TIMEOUT), extract=lambda d: {
        k: d[k] for k in ("id", "title", "author", "comments_count", "comments", "attachments")
    })

    step("Meta.depth=1 в комментариях: статья раскрыта автоматически, автор объявлен явно")
    show(requests.get(api("/api/comments/"), params={"limit": 1}, timeout=TIMEOUT), extract=lambda d: d["results"][0])


def section_files():
    title("6. Работа с файлами")
    john = token_session("john")

    step("john создаёт статью для загрузки файлов")
    response = john.post(
        api("/api/articles/"), json={"title": "Демо: файлы", "content": "Статья с обложкой"}, timeout=TIMEOUT
    )
    article = expect(response, 201).json()
    base = api(f"/api/articles/{article['id']}/")
    print(f"#{article['id']} {article['title']}")

    step("upload_cover: multipart/form-data, PNG с прозрачностью -> миниатюра JPEG")
    show(
        john.post(f"{base}upload_cover/", files={"cover_image": ("cover.png", demo_png(), "image/png")}, timeout=TIMEOUT),
        extract=lambda d: {k: d[k] for k in ("id", "cover_image_url", "cover_thumbnail_url")},
    )

    step("upload_cover без файла: 400")
    show(john.post(f"{base}upload_cover/", data={}, timeout=TIMEOUT))

    step("Не картинка с расширением .png: ImageField проверяет содержимое — 400")
    show(john.post(f"{base}upload_cover/", files={"cover_image": ("fake.png", b"not an image", "image/png")}, timeout=TIMEOUT))

    step("add_attachment: текстовый файл со своим именем")
    show(
        john.post(
            f"{base}add_attachment/",
            files={"file": ("notes.txt", "Конспект".encode(), "text/plain")},
            data={"filename": "Конспект урока.txt"},
            timeout=TIMEOUT,
        )
    )

    step("add_attachment: .exe не пройдёт FileExtensionValidator — 400")
    show(john.post(f"{base}add_attachment/", files={"file": ("virus.exe", b"MZ", "application/octet-stream")}, timeout=TIMEOUT))

    step("add_attachment: файл больше 5 МБ не пройдёт validate_file_size — 400")
    big = b"x" * (5 * 1024 * 1024 + 1)
    show(john.post(f"{base}add_attachment/", files={"file": ("big.txt", big, "text/plain")}, timeout=TIMEOUT))

    step("Статья целиком: обложка, миниатюра и вложения")
    show(john.get(base, timeout=TIMEOUT), extract=lambda d: {
        k: d[k] for k in ("id", "title", "cover_image_url", "cover_thumbnail_url", "attachments")
    })

    step("Откройте ссылки на обложку и миниатюру в браузере. Удаляем демо-статью")
    show(john.delete(base, timeout=TIMEOUT))


def section_throttling():
    title("7. Throttling: ограничение частоты запросов")

    step("Создание статей: BurstRateThrottle, 10 в минуту. Создаём, пока не получим 429")
    john = token_session("john")
    created = []
    for number in range(1, 16):
        response = john.post(
            api("/api/articles/"), json={"title": f"Демо: throttling #{number}", "content": "..."}, timeout=TIMEOUT
        )
        if response.status_code == 429:
            print(f"Создано статей: {len(created)}. Запрос №{number}:")
            show(response)
            print(
                "Если создано меньше 10: лимит burst общий для create и publish, и в него\n"
                "попали статьи, которые john создавал в других разделах за последнюю минуту."
            )
            break
        created.append(response.json()["id"])

    step("Чтение при этом работает: у него свой лимит, SustainedRateThrottle, 100 в час")
    show(john.get(api("/api/articles/"), params={"page_size": 1}, timeout=TIMEOUT), body=False)

    step("Удаляем созданные демо-статьи")
    for article_id in created:
        john.delete(api(f"/api/articles/{article_id}/"), timeout=TIMEOUT)
    print(f"Удалено: {len(created)}")

    step("Лента /api/feed/: SubscriptionRateThrottle, лимит зависит от подписки")
    clients = [
        ("аноним (10/мин)", requests.Session()),
        ("john, free (20/мин)", jwt_session("john")),
        ("editor, basic (60/мин)", jwt_session("editor")),
        ("premium, premium (600/мин)", jwt_session("premium")),
    ]
    for name, client in clients:
        passed = 0
        for _ in range(70):
            response = client.get(api("/api/feed/"), timeout=TIMEOUT)
            if response.status_code == 429:
                break
            passed += 1
        retry = response.headers.get("Retry-After")
        tail = f" -> 429, Retry-After: {retry} с" if response.status_code == 429 else " -> лимит не достигнут"
        print(f"{name:28} прошло запросов: {passed}{tail}")
    print("\nЛимиты считаются за последнюю минуту: если запускали скрипт недавно, пройдёт меньше запросов.")


SECTIONS = {
    "auth": section_auth,
    "permissions": section_permissions,
    "filters": section_filters,
    "pagination": section_pagination,
    "nested": section_nested,
    "files": section_files,
    "throttling": section_throttling,
}


def main():
    global BASE_URL

    parser = argparse.ArgumentParser(description="Демонстрация урока 8 по DRF")
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--only", choices=SECTIONS, help="запустить один раздел")
    parser.add_argument("--pause", action="store_true", help="ждать Enter после каждого раздела")
    args = parser.parse_args()
    BASE_URL = args.base_url.rstrip("/")
    # Консоль Windows со старой кодировкой не должна падать на русских буквах.
    sys.stdout.reconfigure(errors="replace")

    try:
        requests.get(api("/api/"), timeout=TIMEOUT)
    except requests.ConnectionError:
        sys.exit(f"Сервер {BASE_URL} не отвечает. Запустите: python manage.py runserver")

    names = [args.only] if args.only else list(SECTIONS)
    for name in names:
        try:
            SECTIONS[name]()
        except StepFailed as error:
            print(f"\n!!! Раздел «{name}» прерван: {error}")
        if args.pause and name != names[-1]:
            input("\nEnter — следующий раздел...")


if __name__ == "__main__":
    main()
