from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Пользователь блога.

    В методичке у пользователя «предполагаются» два поля. Здесь они настоящие:
      * email_verified — для разрешения HasVerifiedEmail
        (создавать статьи могут только пользователи с подтверждённым email);
      * subscription_level — для SubscriptionRateThrottle
        (чем выше подписка, тем больше запросов можно сделать).
    """

    class Subscription(models.TextChoices):
        FREE = "free", "Бесплатная"
        BASIC = "basic", "Базовая"
        PREMIUM = "premium", "Премиум"

    email_verified = models.BooleanField("email подтверждён", default=False)
    subscription_level = models.CharField(
        "уровень подписки",
        max_length=10,
        choices=Subscription.choices,
        default=Subscription.FREE,
    )

    class Meta(AbstractUser.Meta):
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"
