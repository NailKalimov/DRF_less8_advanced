"""Throttling: ограничение частоты запросов."""

from rest_framework.test import APIRequestFactory
from rest_framework.throttling import UserRateThrottle

from .conftest import client_for

ARTICLES = "/api/articles/"
FEED = "/api/feed/"


def requests_until_429(client, method, url, limit, **kwargs):
    """Сколько запросов прошло до первого 429 (не больше limit)."""
    for number in range(1, limit + 1):
        response = getattr(client, method)(url, **kwargs)
        if response.status_code == 429:
            return number - 1, response
    return limit, response


def test_create_uses_burst_limit(john):
    client = client_for(john)
    passed, response = requests_until_429(
        client, "post", ARTICLES, 20, data={"title": "t", "content": "c"}, format="json"
    )

    assert passed == 10  # burst: 10/minute
    assert response.status_code == 429
    assert int(response["Retry-After"]) > 0


def test_publish_action_uses_its_own_throttle(john, make_article):
    """throttle_classes из @action работают, потому что get_throttles вызывает super()."""
    article = make_article(john, published=False)
    client = client_for(john)
    for _ in range(10):
        client.post(ARTICLES, {"title": "t", "content": "c"}, format="json")

    # create и publish делят лимит burst: после 10 созданий публикация тоже упирается в лимит.
    assert client.post(f"{ARTICLES}{article.id}/publish/").status_code == 429
    # Чтение использует другой лимит (sustained) и всё ещё доступно.
    assert client.get(ARTICLES).status_code == 200


def test_other_actions_use_sustained_limit(john):
    passed, _ = requests_until_429(client_for(john), "get", ARTICLES, 120)

    assert passed == 100  # sustained: 100/hour


def test_subscription_limits_on_feed(api_client, make_user):
    free = make_user("free_user", subscription="free")
    premium = make_user("premium_user", subscription="premium")

    assert requests_until_429(api_client, "get", FEED, 30)[0] == 10  # аноним
    assert requests_until_429(client_for(free), "get", FEED, 30)[0] == 20  # free
    assert requests_until_429(client_for(premium), "get", FEED, 30)[0] == 30  # premium: лимит не достигнут


class LessonSubscriptionRateThrottle(UserRateThrottle):
    """Класс дословно из методички (без get_cache_key, он совпадает с родительским)."""

    def get_rate(self):
        if not hasattr(self, "request"):
            return None
        user = self.request.user
        if user.is_authenticated:
            subscription = getattr(user, "subscription_level", "free")
            rates = {"free": "100/day", "basic": "1000/day", "premium": "10000/day"}
            return rates.get(subscription, "100/day")
        return "50/day"

    def allow_request(self, request, view):
        self.request = request
        return super().allow_request(request, view)


def test_lesson_subscription_throttle_never_limits(db):
    """Вариант из методички не ограничивает никого.

    DRF вычисляет rate один раз в __init__, когда self.request ещё нет,
    поэтому get_rate() возвращает None, а с rate=None allow_request всегда True.
    """
    throttle = LessonSubscriptionRateThrottle()
    request = APIRequestFactory().get(FEED)
    request.user = type("Anon", (), {"is_authenticated": False})()

    assert throttle.rate is None
    assert all(throttle.allow_request(request, view=None) for _ in range(500))
