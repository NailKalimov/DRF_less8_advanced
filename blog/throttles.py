"""Свои классы ограничения частоты запросов (throttling).

Встроенные throttle-классы DRF хранят в кеше историю запросов клиента
и считают, сколько их было за последний период. Когда лимит исчерпан,
клиент получает 429 Too Many Requests и заголовок Retry-After —
через сколько секунд можно повторить.
"""

from rest_framework.throttling import UserRateThrottle


class BurstRateThrottle(UserRateThrottle):
    """Короткий жёсткий лимит для ресурсоёмких операций: 10 в минуту.

    scope — имя лимита в настройке DEFAULT_THROTTLE_RATES.
    """

    scope = "burst"


class SustainedRateThrottle(UserRateThrottle):
    """Длинный мягкий лимит для остальных операций: 100 в час."""

    scope = "sustained"


class SubscriptionRateThrottle(UserRateThrottle):
    """Лимит зависит от уровня подписки пользователя.

    Пользователи с премиум-подпиской могут делать больше запросов,
    и у остальных появляется стимул купить подписку получше.

    get_cache_key берём у UserRateThrottle: для вошедшего пользователя
    ключ строится по его pk, для анонима — по IP-адресу. В методичке этот
    метод переписан, но код в нём совпадает с родительским.

    Отличия от методички:
      * Своя область scope = "subscription". В методичке её нет, и класс
        наследует scope = "user": тогда его история запросов в кеше
        смешается с историей глобального UserRateThrottle.
      * Лимит пересчитывается в allow_request. В методичке allow_request
        только запоминает request, а лимит DRF вычисляет один раз
        в __init__, когда запроса ещё нет. Там get_rate() возвращает None,
        и throttle не ограничивает никого. Это проверяет тест
        tests/test_throttling.py::test_lesson_subscription_throttle_never_limits.
      * Окно — минута, а не день, чтобы лимит было видно на уроке.
        В методичке: anon 50/day, free 100/day, basic 1000/day,
        premium 10000/day.
    """

    scope = "subscription"
    rates = {
        "free": "20/minute",
        "basic": "60/minute",
        "premium": "600/minute",
    }
    anon_rate = "10/minute"  # Для анонимных пользователей.

    def get_rate(self):
        # Пока запроса нет (вызов из __init__), лимит неизвестен.
        if not hasattr(self, "request"):
            return None

        user = self.request.user

        if user.is_authenticated:
            subscription = getattr(user, "subscription_level", "free")
            return self.rates.get(subscription, self.rates["free"])

        return self.anon_rate

    def allow_request(self, request, view):
        self.request = request
        # Пересчитываем лимит для этого пользователя. Без этих двух строк
        # self.rate остался бы None из __init__ и лимит бы не действовал.
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)
