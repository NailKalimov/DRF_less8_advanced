from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Публичные данные автора для вложенных сериализаторов.

    По умолчанию ModelSerializer отдаёт вместо автора только его id,
    и клиенту приходится делать отдельный запрос. Вложенный UserSerializer
    кладёт данные автора прямо в ответ.

    Отличие от методички: email здесь не отдаётся. Статьи и комментарии
    читает кто угодно, в том числе аноним, и email всех авторов утёк бы наружу.
    Свой email пользователь видит в /api/auth/me/.
    """

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name"]


class MeSerializer(serializers.ModelSerializer):
    """Профиль текущего пользователя: GET /api/auth/me/."""

    groups = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name")

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "email_verified",
            "subscription_level",
            "is_staff",
            "groups",
        ]


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Добавляет свои claims в полезную нагрузку JWT.

    Клиент может прочитать эти данные из токена без запросов к серверу.
    Payload только закодирован в base64, а не зашифрован: его прочитает любой,
    у кого есть токен. Пароли и другие секреты туда класть нельзя.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Добавляем кастомные claims.
        token["username"] = user.username
        token["email"] = user.email
        token["is_staff"] = user.is_staff

        return token
