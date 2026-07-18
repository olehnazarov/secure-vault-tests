import re
from http import HTTPStatus

import allure
import pytest

from api.bugs import xfail_bug
from api.endpoints import Assets, Findings

VALID_ASSET_TYPES = {"EC2", "S3", "RDS", "Lambda", "EKS", "VPC"}
NONEXISTENT_ID = "00000000-0000-0000-0000-000000000000"


@allure.title("Create, fetch, and delete an asset of each valid type")
@allure.epic("Assets")
@allure.feature("CRUD")
@allure.tag("positive")
@pytest.mark.parametrize("asset_type", sorted(VALID_ASSET_TYPES))
def test_create_and_get_asset(alpha_admin_client, make_asset_payload, asset_type):
    payload = make_asset_payload(asset_type=asset_type)
    create_res = alpha_admin_client.post(Assets.LIST, json=payload)
    assert create_res.status_code == HTTPStatus.OK
    asset = create_res.json()
    assert asset["asset_type"] == asset_type

    get_res = alpha_admin_client.get(Assets.by_id(asset["id"]))
    assert get_res.status_code == HTTPStatus.OK
    assert get_res.json()["name"] == payload["name"]

    delete_res = alpha_admin_client.delete(Assets.by_id(asset["id"]))
    assert delete_res.status_code == HTTPStatus.OK


@allure.title("Update an asset's name, region, cloud_account, tags, and asset_type")
@allure.epic("Assets")
@allure.feature("CRUD")
@allure.tag("positive")
@xfail_bug(14, "PUT /assets/{id} silently ignores asset_type changes")
def test_update_asset(alpha_admin_client, alpha_asset):
    update_payload = {
        "name": "Renamed Asset",
        "region": "eu-central-1",
        "cloud_account": "222222222222",
        "tags": {"env": "staging"},
        "asset_type": "S3",
    }
    response = alpha_admin_client.put(
        Assets.by_id(alpha_asset["id"]), json=update_payload
    )
    assert response.status_code == HTTPStatus.OK
    response = response.json()
    assert response["name"] == update_payload["name"]
    assert response["region"] == update_payload["region"]
    assert response["cloud_account"] == update_payload["cloud_account"]
    assert response["tags"] == update_payload["tags"]
    assert response["asset_type"] == update_payload["asset_type"]


@allure.title("Reject asset creation with an invalid asset_type")
@allure.epic("Assets")
@allure.feature("Validation")
@allure.tag("negative")
@pytest.mark.parametrize(
    "asset_type", ["NOT_A_REAL_TYPE", ""], ids=["garbage", "empty"]
)
def test_create_asset_invalid_type_is_rejected(
    alpha_admin_client, make_asset_payload, asset_type
):
    response = alpha_admin_client.post(
        Assets.LIST, json=make_asset_payload(asset_type=asset_type)
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST

    detail = response.json()["detail"]
    assert detail.startswith("Invalid asset_type")
    listed_types = set(re.findall(r"'(\w+)'", detail))
    assert listed_types == VALID_ASSET_TYPES


@allure.title("Reject asset creation with empty required fields")
@allure.epic("Assets")
@allure.feature("Validation")
@allure.tag("negative")
@xfail_bug(11, "No content validation on required asset fields")
def test_create_asset_with_empty_fields_is_rejected(
    alpha_admin_client, make_asset_payload
):
    response = alpha_admin_client.post(
        Assets.LIST,
        json=make_asset_payload(name="", cloud_account="", region=""),
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST


@allure.title("Reject asset creation with non-object tags")
@allure.epic("Assets")
@allure.feature("Validation")
@allure.tag("negative")
def test_create_asset_with_invalid_tags_type_is_rejected(
    alpha_admin_client, make_asset_payload
):
    response = alpha_admin_client.post(
        Assets.LIST, json=make_asset_payload(tags="not-an-object")
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@allure.title("Return 404 for GET/PUT/DELETE on a nonexistent asset ID")
@allure.epic("Assets")
@allure.feature("Validation")
@allure.tag("negative")
@pytest.mark.parametrize(
    "method, kwargs",
    [
        ("get", {}),
        ("put", {"json": {"name": "does-not-matter"}}),
        ("delete", {}),
    ],
    ids=["get", "put", "delete"],
)
def test_nonexistent_asset_id_returns_404(alpha_admin_client, method, kwargs):
    response = getattr(alpha_admin_client, method)(
        Assets.by_id(NONEXISTENT_ID), **kwargs
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


@allure.title("Analyst role cannot create an asset")
@allure.epic("Assets")
@allure.feature("RBAC")
@allure.tag("negative")
@xfail_bug(
    5, "RBAC bypass - analyst can create/trigger resources (/assets, /findings, /scans)"
)
def test_analyst_cannot_create_asset(alpha_analyst_client, make_asset_payload):
    response = alpha_analyst_client.post(Assets.LIST, json=make_asset_payload())
    assert response.status_code == HTTPStatus.FORBIDDEN


@allure.title("Analyst role can list and fetch assets")
@allure.epic("Assets")
@allure.feature("RBAC")
@allure.tag("positive")
def test_analyst_can_read_assets(alpha_analyst_client, alpha_asset):
    list_res = alpha_analyst_client.get(Assets.LIST)
    assert list_res.status_code == HTTPStatus.OK
    assert "items" in list_res.json()

    get_res = alpha_analyst_client.get(Assets.by_id(alpha_asset["id"]))
    assert get_res.status_code == HTTPStatus.OK
    assert get_res.json()["id"] == alpha_asset["id"]


@allure.title("Analyst role cannot delete an asset")
@allure.epic("Assets")
@allure.feature("RBAC")
@allure.tag("negative")
def test_analyst_cannot_delete_asset(alpha_analyst_client, alpha_asset):
    response = alpha_analyst_client.delete(Assets.by_id(alpha_asset["id"]))
    assert response.status_code == HTTPStatus.FORBIDDEN


@allure.title("Analyst role cannot update an asset")
@allure.epic("Assets")
@allure.feature("RBAC")
@allure.tag("negative")
def test_analyst_cannot_update_asset(alpha_analyst_client, alpha_asset):
    response = alpha_analyst_client.put(
        Assets.by_id(alpha_asset["id"]), json={"name": "hacked-by-analyst"}
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@allure.title("Reject deleting an asset that has open findings")
@allure.epic("Assets")
@allure.feature("Business Rules")
@allure.tag("negative")
@xfail_bug(
    3, "DELETE asset with open findings returns 500 with stack trace instead of 409"
)
def test_cannot_delete_asset_with_open_findings(
    alpha_admin_client, alpha_asset, make_finding_payload
):
    finding_res = alpha_admin_client.post(
        Findings.LIST, json=make_finding_payload(alpha_asset["id"])
    )
    assert finding_res.status_code == HTTPStatus.OK

    delete_res = alpha_admin_client.delete(Assets.by_id(alpha_asset["id"]))
    assert delete_res.status_code == HTTPStatus.CONFLICT
