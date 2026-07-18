import uuid
from http import HTTPStatus
from typing import Iterator

import httpx
import pytest

from api.api_client import ApiClient
from api.endpoints import Assets, Auth, Health
from config import BASE_URL, USERS


@pytest.fixture(scope="session", autouse=True)
def _service_health_check():
    """Gates the whole run on the API being reachable."""
    try:
        response = httpx.get(f"{BASE_URL}{Health.CHECK}", timeout=5.0)
    except httpx.HTTPError as exc:
        pytest.exit(f"SecureVault API unreachable at {BASE_URL}: {exc}", returncode=1)

    if response.status_code != HTTPStatus.OK:
        pytest.exit(
            f"SecureVault API is not healthy at {BASE_URL}: "
            f"{response.status_code} {response.text}",
            returncode=1,
        )


@pytest.fixture(scope="session")
def api_client():
    with ApiClient(base_url=BASE_URL) as client:
        yield client


def get_tokens_for_user(client, email, password):
    response = client.post(Auth.LOGIN, json={"email": email, "password": password})
    assert (
        response.status_code == HTTPStatus.OK
    ), f"Failed to login user {email}: {response.text}"
    data = response.json()
    return data["access_token"], data["refresh_token"]


def _client_for(api_client, user_key: str) -> Iterator[ApiClient]:
    """Logs in as `user_key` (see config.USERS) and yields an authenticated API client."""
    user = USERS[user_key]
    token, _ = get_tokens_for_user(api_client, user["email"], user["password"])
    with ApiClient(
        base_url=BASE_URL, headers={"Authorization": f"Bearer {token}"}
    ) as client:
        yield client


@pytest.fixture(scope="session")
def alpha_admin_client(api_client):
    yield from _client_for(api_client, "alpha_admin")


@pytest.fixture(scope="session")
def alpha_analyst_client(api_client):
    yield from _client_for(api_client, "alpha_analyst")


@pytest.fixture(scope="session")
def beta_admin_client(api_client):
    yield from _client_for(api_client, "beta_admin")


@pytest.fixture
def unique_suffix():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def make_asset_payload(unique_suffix):
    """Factory for a valid AssetCreate payload; pass overrides to break specific fields."""

    def _factory(**overrides):
        payload = {
            "name": f"Test Asset {unique_suffix}",
            "asset_type": "EC2",
            "cloud_account": "123456789012",
            "region": "us-east-1",
        }
        payload.update(overrides)
        return payload

    return _factory


@pytest.fixture
def make_finding_payload(unique_suffix):
    """Factory for a valid FindingCreate payload; requires an asset_id."""

    def _factory(asset_id, **overrides):
        payload = {
            "title": f"Test Finding {unique_suffix}",
            "severity": "MEDIUM",
            "asset_id": asset_id,
        }
        payload.update(overrides)
        return payload

    return _factory


@pytest.fixture
def alpha_asset(alpha_admin_client, make_asset_payload):
    """Creates a temporary asset in org-alpha and deletes it afterward"""
    response = alpha_admin_client.post(Assets.LIST, json=make_asset_payload())
    # openapi.json declares 201 for this route, but the live API actually returns 200.
    assert response.status_code == HTTPStatus.OK, response.text
    asset = response.json()
    yield asset
    try:
        alpha_admin_client.delete(Assets.by_id(asset["id"]))
    except httpx.HTTPError:
        pass  # safety cleanup the asset may already been removed
