from http import HTTPStatus

import allure
import pytest

from api.api_client import ApiClient
from api.bugs import xfail_bug
from api.endpoints import Assets, Auth, Findings, Reports, Scans
from config import BASE_URL, USERS

NONEXISTENT_ID = "00000000-0000-0000-0000-000000000000"

# One representative endpoint per resource - this is about verifying the
# no-token-rejected pattern holds everywhere, not exhaustively covering every route.
NO_TOKEN_CASES = [
    ("get", Assets.LIST),
    ("post", Assets.LIST),
    ("get", Assets.by_id(NONEXISTENT_ID)),
    ("put", Assets.by_id(NONEXISTENT_ID)),
    ("delete", Assets.by_id(NONEXISTENT_ID)),
    ("get", Findings.LIST),
    ("post", Findings.LIST),
    ("patch", Findings.status(NONEXISTENT_ID)),
    ("post", Scans.LIST),
    ("get", Scans.status(NONEXISTENT_ID)),
    ("get", Reports.SUMMARY),
]


@allure.title("Login with valid credentials returns access and refresh tokens")
@allure.epic("Authentication")
@allure.feature("Session")
@allure.story("Login")
@allure.tag("positive")
def test_login_success(api_client):
    user = USERS["alpha_admin"]
    response = api_client.post(
        Auth.LOGIN, json={"email": user["email"], "password": user["password"]}
    )
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@allure.title("Login with the wrong password is rejected")
@allure.epic("Authentication")
@allure.feature("Session")
@allure.story("Login")
@allure.tag("negative")
def test_login_invalid_credentials(api_client):
    user = USERS["alpha_admin"]
    response = api_client.post(
        Auth.LOGIN,
        json={"email": user["email"], "password": "definitely-wrong-password"},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@allure.title("Login with an unknown email is rejected")
@allure.epic("Authentication")
@allure.feature("Session")
@allure.story("Login")
@allure.tag("negative")
def test_login_unknown_user(api_client):
    response = api_client.post(
        Auth.LOGIN, json={"email": "nobody@org-alpha.com", "password": "whatever123"}
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@allure.title("Requests without an auth token are rejected across all endpoints")
@allure.epic("Authentication")
@allure.feature("Authorization")
@allure.tag("negative")
@xfail_bug(9, "Unauthenticated request returns 403 instead of documented 401")
@pytest.mark.parametrize(
    "method, path", NO_TOKEN_CASES, ids=[f"{m.upper()} {p}" for m, p in NO_TOKEN_CASES]
)
def test_request_without_token_is_rejected(api_client, method, path):
    kwargs = {"json": {}} if method in ("post", "put", "patch") else {}
    response = getattr(api_client, method)(path, **kwargs)
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@allure.title("Request with an invalid bearer token is rejected")
@allure.epic("Authentication")
@allure.feature("Authorization")
@allure.tag("negative")
def test_request_with_invalid_token_is_rejected(api_client):
    response = ApiClient(
        base_url=BASE_URL, headers={"Authorization": "Bearer not-a-token"}
    ).get(Assets.LIST)
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@allure.title("Access token is rejected after logout")
@allure.epic("Authentication")
@allure.feature("Session")
@allure.story("Logout")
@allure.tag("negative")
@xfail_bug(10, "Access token remains valid after logout")
def test_access_token_rejected_after_logout(api_client):
    user = USERS["alpha_admin"]
    login_res = api_client.post(
        Auth.LOGIN, json={"email": user["email"], "password": user["password"]}
    )
    access_token = login_res.json()["access_token"]
    refresh_token = login_res.json()["refresh_token"]

    logout_res = api_client.post(Auth.LOGOUT, json={"refresh_token": refresh_token})
    assert logout_res.status_code == HTTPStatus.OK

    response = ApiClient(
        base_url=BASE_URL, headers={"Authorization": f"Bearer {access_token}"}
    ).get(Assets.LIST)
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@allure.title("Refresh token can only be used once")
@allure.epic("Authentication")
@allure.feature("Session")
@allure.story("Refresh Token")
@allure.severity(allure.severity_level.CRITICAL)
@allure.tag("negative")
@xfail_bug(2, "Refresh token is not one-time use")
def test_one_time_refresh_token(api_client):
    user = USERS["alpha_admin"]
    login_res = api_client.post(
        Auth.LOGIN, json={"email": user["email"], "password": user["password"]}
    )
    refresh_token = login_res.json()["refresh_token"]

    refresh_res1 = api_client.post(Auth.REFRESH, json={"refresh_token": refresh_token})
    assert refresh_res1.status_code == HTTPStatus.OK
    assert (
        refresh_res1.json()["refresh_token"] != refresh_token
    ), "a new refresh token must be issued"

    refresh_res2 = api_client.post(Auth.REFRESH, json={"refresh_token": refresh_token})
    assert (
        refresh_res2.status_code == HTTPStatus.UNAUTHORIZED
    ), "Reusing an already-consumed refresh token must be rejected"


@allure.title("Logout revokes the refresh token")
@allure.epic("Authentication")
@allure.feature("Session")
@allure.story("Logout")
@allure.tag("negative")
def test_logout_revokes_refresh_token(api_client):
    user = USERS["alpha_admin"]
    login_res = api_client.post(
        Auth.LOGIN, json={"email": user["email"], "password": user["password"]}
    )
    refresh_token = login_res.json()["refresh_token"]

    logout_res = api_client.post(Auth.LOGOUT, json={"refresh_token": refresh_token})
    assert logout_res.status_code == HTTPStatus.OK

    refresh_after_logout = api_client.post(
        Auth.REFRESH, json={"refresh_token": refresh_token}
    )
    assert refresh_after_logout.status_code == HTTPStatus.UNAUTHORIZED


@allure.title("Login is throttled after 10 requests per minute")
@pytest.mark.rate_limit
@allure.epic("Authentication")
@allure.feature("Session")
@allure.story("Rate Limiting")
@allure.tag("negative")
def test_login_rate_limit(api_client):
    """
    Excluded from the default run (see pytest.ini `-m "not rate_limit"`) and must be run
    in isolation with `pytest -m rate_limit`: it deliberately burns the 10 req/min login
    quota, which would otherwise starve every other test needing a fresh login.
    """
    user = USERS["alpha_admin"]
    statuses = []
    for _ in range(11):
        response = api_client.post(
            Auth.LOGIN,
            json={
                "email": user["email"],
                "password": user["password"],
            },
        )
        statuses.append(response.status_code)

    assert (
        statuses[:10] == [HTTPStatus.OK] * 10
    ), f"expected the first 10 requests/minute to succeed, got: {statuses[:10]}"
    assert (
        statuses[10] == HTTPStatus.TOO_MANY_REQUESTS
    ), f"expected the 11th request to be throttled with 429, got: {statuses[10]}"
