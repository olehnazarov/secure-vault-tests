from http import HTTPStatus

import allure
import pytest

from api.endpoints import Findings
from api.models import FindingStatus, Severity

NONEXISTENT_ID = "00000000-0000-0000-0000-000000000000"


@allure.title(
    "Finding moves through its status lifecycle while severity stays immutable"
)
@allure.epic("Findings")
@allure.feature("Lifecycle")
@allure.tag("positive")
def test_finding_lifecycle_and_severity_immutability(
    alpha_admin_client, alpha_asset, make_finding_payload
):
    finding_res = alpha_admin_client.post(
        Findings.LIST,
        json=make_finding_payload(alpha_asset["id"], severity=Severity.MEDIUM),
    )
    # openapi.json declares 201 for this route, but the live API actually returns 200.
    assert finding_res.status_code == HTTPStatus.OK
    finding_id = finding_res.json()["id"]
    assert finding_res.json()["status"] == FindingStatus.OPEN

    patch_res = alpha_admin_client.patch(
        Findings.status(finding_id), json={"status": FindingStatus.MITIGATED}
    )
    assert patch_res.status_code == HTTPStatus.OK
    assert patch_res.json()["status"] == FindingStatus.MITIGATED

    # severity is set at creation and must be immutable via status update, even if sent
    patch_severity_res = alpha_admin_client.patch(
        Findings.status(finding_id),
        json={
            "status": FindingStatus.CLOSED,
            "severity": Severity.LOW,
        },
    )
    assert patch_severity_res.status_code == HTTPStatus.OK
    assert patch_severity_res.json()["status"] == FindingStatus.CLOSED
    assert patch_severity_res.json()["severity"] == Severity.MEDIUM


@allure.title("Analyst role can list findings for an asset")
@allure.epic("Findings")
@allure.feature("RBAC")
@allure.tag("positive")
def test_analyst_can_read_findings(
    alpha_admin_client, alpha_analyst_client, alpha_asset, make_finding_payload
):
    finding_res = alpha_admin_client.post(
        Findings.LIST, json=make_finding_payload(alpha_asset["id"])
    )
    finding_id = finding_res.json()["id"]

    list_res = alpha_analyst_client.get(
        Findings.LIST, params={"asset_id": alpha_asset["id"]}
    )
    assert list_res.status_code == HTTPStatus.OK
    assert any(f["id"] == finding_id for f in list_res.json()["items"])


@allure.title("Return 404 when updating status of a nonexistent finding")
@allure.epic("Findings")
@allure.feature("Validation")
@allure.tag("negative")
def test_update_status_for_nonexistent_finding_returns_404(alpha_admin_client):
    response = alpha_admin_client.patch(
        Findings.status(NONEXISTENT_ID), json={"status": FindingStatus.MITIGATED}
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


@allure.title("Reject invalid finding status transitions")
@allure.epic("Findings")
@allure.feature("Lifecycle")
@allure.tag("negative")
@pytest.mark.xfail(
    reason="BUG: PATCH /findings/{id}/status does not enforce the "
    "open -> mitigated -> closed state machine - both a skip-ahead "
    "(open -> closed) and a backward (closed -> open) transition return 200 "
    "instead of being rejected.",
    strict=True,
)
@pytest.mark.parametrize(
    "setup_statuses, target_status",
    [
        ([], FindingStatus.CLOSED),
        ([FindingStatus.MITIGATED, FindingStatus.CLOSED], FindingStatus.OPEN),
    ],
    ids=["skip-ahead open->closed", "backward closed->open"],
)
def test_invalid_status_transition_is_rejected(
    alpha_admin_client, alpha_asset, make_finding_payload, setup_statuses, target_status
):
    finding_id = alpha_admin_client.post(
        Findings.LIST, json=make_finding_payload(alpha_asset["id"])
    ).json()["id"]

    for status in setup_statuses:
        alpha_admin_client.patch(Findings.status(finding_id), json={"status": status})

    response = alpha_admin_client.patch(
        Findings.status(finding_id), json={"status": target_status}
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST


@allure.title("Analyst role can update a finding's status")
@allure.epic("Findings")
@allure.feature("RBAC")
@allure.tag("positive")
def test_analyst_can_update_finding_status(
    alpha_admin_client, alpha_analyst_client, alpha_asset, make_finding_payload
):
    finding_res = alpha_admin_client.post(
        Findings.LIST, json=make_finding_payload(alpha_asset["id"])
    )
    finding_id = finding_res.json()["id"]

    patch_res = alpha_analyst_client.patch(
        Findings.status(finding_id), json={"status": FindingStatus.MITIGATED}
    )
    assert patch_res.status_code == HTTPStatus.OK
    assert patch_res.json()["status"] == FindingStatus.MITIGATED


@allure.title("Analyst role cannot create a finding")
@allure.epic("Findings")
@allure.feature("RBAC")
@allure.tag("negative")
@pytest.mark.xfail(
    reason="https://github.com/olehnazarov/secure-vault-tests/issues/5 - "
    "analyst role can create findings via POST /findings (got 200), "
    "Product Overview restricts analyst to read access plus status updates only",
    strict=True,
)
def test_analyst_cannot_create_finding(
    alpha_analyst_client, alpha_asset, make_finding_payload
):
    response = alpha_analyst_client.post(
        Findings.LIST, json=make_finding_payload(alpha_asset["id"])
    )
    assert response.status_code == HTTPStatus.FORBIDDEN


@allure.title("Reject creating a finding for a nonexistent asset")
@allure.epic("Findings")
@allure.feature("Validation")
@allure.tag("negative")
def test_create_finding_for_nonexistent_asset_fails(
    alpha_admin_client, make_finding_payload
):
    response = alpha_admin_client.post(
        Findings.LIST,
        json=make_finding_payload(NONEXISTENT_ID),
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


@allure.title("Reject creating a finding with an invalid severity")
@allure.epic("Findings")
@allure.feature("Validation")
@allure.tag("negative")
def test_create_finding_invalid_severity_is_rejected(
    alpha_admin_client, alpha_asset, make_finding_payload
):
    response = alpha_admin_client.post(
        Findings.LIST,
        json=make_finding_payload(alpha_asset["id"], severity="NOT_A_SEVERITY"),
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST


@allure.title("Filter findings by severity and asset ID")
@allure.epic("Findings")
@allure.feature("Filtering")
@allure.tag("positive")
def test_filter_findings_by_severity_and_asset(
    alpha_admin_client, alpha_asset, make_finding_payload
):
    alpha_admin_client.post(
        Findings.LIST,
        json=make_finding_payload(alpha_asset["id"], severity=Severity.CRITICAL),
    )

    response = alpha_admin_client.get(
        Findings.LIST,
        params={
            "severity": Severity.CRITICAL,
            "asset_id": alpha_asset["id"],
        },
    )
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["total"] >= 1
    assert all(f["severity"] == Severity.CRITICAL for f in body["items"])
    assert all(f["asset_id"] == alpha_asset["id"] for f in body["items"])


@allure.title("Severity filter on GET /findings is case-insensitive")
@allure.epic("Findings")
@allure.feature("Filtering")
@allure.tag("positive")
@pytest.mark.xfail(
    reason="BUG: severity/status filters on GET /findings are case-sensitive "
    "(severity=high returns 0 results while severity=HIGH returns matches), "
    "contradicting the documented 'Case-Insensitive Filters' rule.",
    strict=True,
)
def test_severity_filter_is_case_insensitive(
    alpha_admin_client, alpha_asset, make_finding_payload
):
    alpha_admin_client.post(
        Findings.LIST,
        json=make_finding_payload(alpha_asset["id"], severity=Severity.HIGH),
    )

    upper = alpha_admin_client.get(
        Findings.LIST, params={"severity": Severity.HIGH, "asset_id": alpha_asset["id"]}
    )
    lower = alpha_admin_client.get(
        Findings.LIST,
        params={"severity": Severity.HIGH.lower(), "asset_id": alpha_asset["id"]},
    )

    assert upper.status_code == HTTPStatus.OK and lower.status_code == HTTPStatus.OK
    assert lower.json()["total"] == upper.json()["total"]
    assert lower.json()["total"] >= 1


@allure.title("Filter findings by status")
@allure.epic("Findings")
@allure.feature("Filtering")
@allure.tag("positive")
def test_filter_findings_by_status(
    alpha_admin_client, alpha_asset, make_finding_payload
):
    finding_res = alpha_admin_client.post(
        Findings.LIST, json=make_finding_payload(alpha_asset["id"])
    )
    finding_id = finding_res.json()["id"]

    response = alpha_admin_client.get(
        Findings.LIST,
        params={"status": FindingStatus.OPEN, "asset_id": alpha_asset["id"]},
    )
    assert response.status_code == HTTPStatus.OK
    assert any(f["id"] == finding_id for f in response.json()["items"])

    alpha_admin_client.patch(
        Findings.status(finding_id), json={"status": FindingStatus.MITIGATED}
    )
    response = alpha_admin_client.get(
        Findings.LIST,
        params={"status": FindingStatus.OPEN, "asset_id": alpha_asset["id"]},
    )
    assert all(f["id"] != finding_id for f in response.json()["items"])


@allure.title("Status filter on GET /findings is case-insensitive")
@allure.epic("Findings")
@allure.feature("Filtering")
@allure.tag("positive")
@pytest.mark.xfail(
    reason="BUG: the `status` filter on GET /findings is case-sensitive too "
    "(status=open returns matches, status=OPEN returns 0), same root cause "
    "as the severity filter bug.",
    strict=True,
)
def test_status_filter_is_case_insensitive(
    alpha_admin_client, alpha_asset, make_finding_payload
):
    alpha_admin_client.post(Findings.LIST, json=make_finding_payload(alpha_asset["id"]))

    lower = alpha_admin_client.get(
        Findings.LIST,
        params={"status": FindingStatus.OPEN, "asset_id": alpha_asset["id"]},
    )
    upper = alpha_admin_client.get(
        Findings.LIST,
        params={"status": FindingStatus.OPEN.upper(), "asset_id": alpha_asset["id"]},
    )

    assert lower.status_code == HTTPStatus.OK and upper.status_code == HTTPStatus.OK
    assert lower.json()["total"] == upper.json()["total"]
    assert upper.json()["total"] >= 1


@allure.title("Findings list respects page and limit pagination params")
@allure.epic("Findings")
@allure.feature("Pagination")
@allure.tag("positive")
def test_findings_list_is_paginated(alpha_admin_client):
    response = alpha_admin_client.get(Findings.LIST, params={"page": 1, "limit": 5})
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["page"] == 1
    assert body["limit"] == 5
    assert len(body["items"]) <= 5
