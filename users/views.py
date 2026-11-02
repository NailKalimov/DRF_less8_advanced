"""Аутентификация: Token, JWT и проверка «кто я».

Аутентификация отвечает на вопрос «кто вы?», авторизация — «что вам разрешено?».
В DRF первое делают классы Authentication, второе — классы Permission.
Сначала DRF определяет пользователя, затем проверяет его права.
"""

from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import CustomTokenObtainPairSerializer, MeSerializer


@api_view(["POST"])
@permission_classes([AllowAny])
def custom_login(request):
    """Вход по логину и паролю с выдачей DRF-токена и данных пользователя.

    Встроенный obtain_auth_token возвращает только {"token": "..."}.
    Своё представление даёт больше контроля: в ответ можно добавить
    любую нужную информацию о пользователе.

    Токен — случайная строка, связанная с пользователем в базе данных.
    Он действует, пока его явно не удалят (см. token_logout).
    Клиент передаёт его в каждом запросе:
        Authorization: Token <ключ>
    """
    username = request.data.get("username")
    password = request.data.get("password")

    user = authenticate(username=username, password=password)

    if user is not None:
        token, created = Token.objects.get_or_create(user=user)
        return Response(
            {
                "token": token.key,
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
            }
        )
    return Response(
        {"error": "Неверные учетные данные"},
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def token_logout(request):
    """Выход: удаляет DRF-токен пользователя.

    Этого эндпоинта нет в методичке. Он показывает, что DRF-токен действует
    до явного удаления: после выхода старый токен даёт 401.
    """
    Token.objects.filter(user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


class CustomTokenObtainPairView(TokenObtainPairView):
    """Выдаёт пару JWT (access и refresh) с дополнительными claims."""

    serializer_class = CustomTokenObtainPairSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    """Кто я и каким способом вошёл.

    Этого эндпоинта нет в методичке. Он удобен на уроке: поле authenticated_via
    показывает, какой класс аутентификации опознал пользователя
    (JWTAuthentication, TokenAuthentication или SessionAuthentication).
    Без входа ответ — 401 Unauthorized: так работает IsAuthenticated.
    """
    data = MeSerializer(request.user).data
    data["authenticated_via"] = type(request.successful_authenticator).__name__
    return Response(data)
