"""Аутентификация: Session, Token и JWT."""

import base64
import json

from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework.views import APIView

from .conftest import PASSWORD

ME = "/api/auth/me/"


def jwt_payload(token):
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def test_anonymous_gets_401_with_bearer_challenge(api_client, db):
    response = api_client.get(ME)

    assert response.status_code == 401
    # Первый класс аутентификации — JWT, поэтому заголовок Bearer, а ответ 401, а не 403.
    assert response["WWW-Authenticate"].startswith("Bearer")


def test_session_authentication_first_turns_401_into_403(db):
    """Почему SessionAuthentication не стоит первым в DEFAULT_AUTHENTICATION_CLASSES.

    У SessionAuthentication нет заголовка WWW-Authenticate, а ответ 401
    без этого заголовка не отправляют. Поэтому DRF меняет 401 на 403.
    """

    class SessionFirstView(APIView):
        authentication_classes = [SessionAuthentication, TokenAuthentication]
        permission_classes = [IsAuthenticated]

        def get(self, request):
            return Response({})

    response = SessionFirstView.as_view()(APIRequestFactory().get("/"))

    assert response.status_code == 403


def test_obtain_auth_token_and_use_it(api_client, john):
    response = api_client.post("/api/auth/obtain-token/", {"username": "john", "password": PASSWORD})
    assert response.status_code == 200
    token = response.data["token"]

    api_client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
    me = api_client.get(ME)

    assert me.status_code == 200
    assert me.data["username"] == "john"
    assert me.data["authenticated_via"] == "TokenAuthentication"


def test_custom_login_returns_user_info(api_client, john):
    response = api_client.post("/api/auth/login/", {"username": "john", "password": PASSWORD})

    assert response.status_code == 200
    assert set(response.data) == {"token", "user_id", "username", "email"}
    assert response.data["user_id"] == john.id
    assert Token.objects.get(user=john).key == response.data["token"]


def test_custom_login_wrong_password(api_client, john):
    response = api_client.post("/api/auth/login/", {"username": "john", "password": "wrong"})

    assert response.status_code == 400
    assert response.data == {"error": "Неверные учетные данные"}


def test_logout_deletes_token(api_client, john):
    token = Token.objects.create(user=john)
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    assert api_client.post("/api/auth/logout/").status_code == 204
    assert api_client.get(ME).status_code == 401


def test_jwt_pair_contains_custom_claims(api_client, john):
    response = api_client.post("/api/auth/token/", {"username": "john", "password": PASSWORD})
    assert response.status_code == 200

    payload = jwt_payload(response.data["access"])
    assert payload["username"] == "john"
    assert payload["email"] == "john@example.com"
    assert payload["is_staff"] is False

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    me = api_client.get(ME)
    assert me.data["authenticated_via"] == "JWTAuthentication"


def test_jwt_refresh_rotates_and_blacklists_old_token(api_client, john):
    pair = api_client.post("/api/auth/token/", {"username": "john", "password": PASSWORD}).data

    refreshed = api_client.post("/api/auth/token/refresh/", {"refresh": pair["refresh"]})
    assert refreshed.status_code == 200
    # ROTATE_REFRESH_TOKENS=True: вместе с access приходит новый refresh.
    assert refreshed.data["refresh"] != pair["refresh"]

    # BLACKLIST_AFTER_ROTATION=True: старый refresh больше не работает.
    reused = api_client.post("/api/auth/token/refresh/", {"refresh": pair["refresh"]})
    assert reused.status_code == 401


def test_jwt_blacklist_endpoint(api_client, john):
    pair = api_client.post("/api/auth/token/", {"username": "john", "password": PASSWORD}).data

    assert api_client.post("/api/auth/token/blacklist/", {"refresh": pair["refresh"]}).status_code == 200
    assert api_client.post("/api/auth/token/refresh/", {"refresh": pair["refresh"]}).status_code == 401


def test_session_authentication(john):
    client = APIClient()
    client.login(username="john", password=PASSWORD)

    me = client.get(ME)
    assert me.data["authenticated_via"] == "SessionAuthentication"


def test_session_authentication_requires_csrf_for_unsafe_methods(john):
    client = APIClient(enforce_csrf_checks=True)
    client.login(username="john", password=PASSWORD)

    response = client.post("/api/articles/", {"title": "t", "content": "c"}, format="json")

    assert response.status_code == 403
    assert "CSRF" in str(response.data["detail"])
