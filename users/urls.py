"""Маршруты аутентификации, все с префиксом /api/auth/."""

from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from . import views

urlpatterns = [
    # --- Token Authentication ---
    # Готовое представление DRF: POST {"username", "password"} -> {"token"}.
    path("obtain-token/", obtain_auth_token, name="api_token_auth"),
    # Своё представление: токен и данные пользователя.
    path("login/", views.custom_login, name="custom_login"),
    # Удаление токена.
    path("logout/", views.token_logout, name="token_logout"),
    # --- JWT ---
    # Пара токенов: POST {"username", "password"} -> {"access", "refresh"}.
    path("token/", views.CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    # Новый access token по refresh token: POST {"refresh"}.
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # Выход для JWT: refresh token попадает в чёрный список.
    path("token/blacklist/", TokenBlacklistView.as_view(), name="token_blacklist"),
    # --- Кто я ---
    path("me/", views.me, name="me"),
]
