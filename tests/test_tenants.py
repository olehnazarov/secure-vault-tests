from http import HTTPStatus

import allure
import pytest

from api.endpoints import Assets, Findings, Reports, Scans
from config import USERS


@allure.title("Asset from one org is not listed in another org's asset list")
@allure.epic("Multi-tenancy")
@allure.feature("Data Isolation")
@allure.story("GET /assets")
@allure.tag("negative")
def test_asset_not_listed_across_organizations(
    alpha_admin_client, beta_admin_client, make_asset_payload
):
    alpha_asset_res = alpha_admin_client.post(Assets.LIST, json=make_asset_payload())
    alpha_asset_id = alpha_asset_res.json()["id"]

    beta_list_res = beta_admin_client.get(Assets.LIST, params={"limit": 100})
    assert beta_list_res.status_code == HTTPStatus.OK
    assert all(item["id"] != alpha_asset_id for item in beta_list_res.json()["items"])

    alpha_admin_client.delete(Assets.by_id(alpha_asset_id))


@allure.title("Cross-org user cannot read another org's asset by ID")
@allure.epic("Multi-tenancy")
@allure.feature("Data Isolation")
@allure.story("GET /assets/{id}")
@allure.severity(allure.severity_level.BLOCKER)
@allure.tag("negative")
@pytest.mark.xfail(
    reason="https://github.com/olehnazarov/secure-vault-tests/issues/1 - "
    "IDOR - no org check on direct resource access",
    strict=True,
)
def test_cross_org_user_cannot_read_asset_by_id(
    alpha_admin_client, beta_admin_client, alpha_asset
):
    beta_get_res = beta_admin_client.get(Assets.by_id(alpha_asset["id"]))
    assert beta_get_res.status_code == HTTPStatus.NOT_FOUND


@allure.title("Cross-org user cannot update another org's asset by ID")
@allure.epic("Multi-tenancy")
@allure.feature("Data Isolation")
@allure.story("PUT /assets/{id}")
@allure.severity(allure.severity_level.BLOCKER)
@allure.tag("negative")
@pytest.mark.xfail(
    reason="https://github.com/olehnazarov/secure-vault-tests/issues/1 - "
    "IDOR - no org check on direct resource access",
    strict=True,
)
def test_cross_org_user_cannot_update_asset_by_id(
    alpha_admin_client, beta_admin_client, alpha_asset
):
    beta_put_res = beta_admin_client.put(
        Assets.by_id(alpha_asset["id"]), json={"name": "hacked-by-beta"}
    )
    assert beta_put_res.status_code == HTTPStatus.NOT_FOUND


@allure.title("Cross-org user cannot delete another org's asset by ID")
@allure.epic("Multi-tenancy")
@allure.feature("Data Isolation")
@allure.story("DELETE /assets/{id}")
@allure.severity(allure.severity_level.BLOCKER)
@allure.tag("negative")
@pytest.mark.xfail(
    reason="https://github.com/olehnazarov/secure-vault-tests/issues/1 - "
    "IDOR - no org check on direct resource access",
    strict=True,
)
def test_cross_org_user_cannot_delete_asset_by_id(
    alpha_admin_client, beta_admin_client, make_asset_payload
):
    # Creates its own asset instead of alpha_asset: this test deletes it itself, and
    # reusing the fixture would double-delete during its teardown.
    alpha_asset_res = alpha_admin_client.post(Assets.LIST, json=make_asset_payload())
    alpha_asset_id = alpha_asset_res.json()["id"]

    try:
        beta_delete_res = beta_admin_client.delete(Assets.by_id(alpha_asset_id))
        assert beta_delete_res.status_code == HTTPStatus.NOT_FOUND
    finally:
        alpha_admin_client.delete(Assets.by_id(alpha_asset_id))


@allure.title("Cross-org user cannot update another org's finding status")
@allure.epic("Multi-tenancy")
@allure.feature("Data Isolation")
@allure.story("PATCH /findings/{id}/status")
@allure.severity(allure.severity_level.BLOCKER)
@allure.tag("negative")
@pytest.mark.xfail(
    reason="https://github.com/olehnazarov/secure-vault-tests/issues/1 - "
    "IDOR - no org check on direct resource access",
    strict=True,
)
def test_cross_org_user_cannot_update_finding_status(
    alpha_admin_client, beta_admin_client, alpha_asset, make_finding_payload
):
    finding_res = alpha_admin_client.post(
        Findings.LIST, json=make_finding_payload(alpha_asset["id"])
    )
    finding_id = finding_res.json()["id"]

    beta_patch_res = beta_admin_client.patch(
        Findings.status(finding_id), json={"status": "closed"}
    )
    assert beta_patch_res.status_code == HTTPStatus.NOT_FOUND


@allure.title("Findings are isolated between organizations")
@allure.epic("Multi-tenancy")
@allure.feature("Data Isolation")
@allure.story("GET /findings")
@allure.tag("negative")
def test_findings_isolation_between_organizations(
    alpha_admin_client, beta_admin_client, alpha_asset, make_finding_payload
):
    alpha_admin_client.post(Findings.LIST, json=make_finding_payload(alpha_asset["id"]))

    beta_view_res = beta_admin_client.get(
        Findings.LIST, params={"asset_id": alpha_asset["id"]}
    )
    assert beta_view_res.status_code == HTTPStatus.OK
    assert beta_view_res.json()["total"] == 0
    assert beta_view_res.json()["items"] == []


@allure.title("Reject creating a finding for another org's asset")
@allure.epic("Multi-tenancy")
@allure.feature("Data Isolation")
@allure.story("POST /findings")
@allure.tag("negative")
def test_create_finding_for_cross_org_asset_fails(
    beta_admin_client, alpha_asset, make_finding_payload
):
    response = beta_admin_client.post(
        Findings.LIST, json=make_finding_payload(alpha_asset["id"])
    )
    assert response.status_code == HTTPStatus.NOT_FOUND


@allure.title("Scan status is isolated between organizations")
@allure.epic("Multi-tenancy")
@allure.feature("Data Isolation")
@allure.story("GET /scans/{id}/status")
@allure.tag("negative")
def test_scan_status_isolation_between_organizations(
    alpha_admin_client, beta_admin_client
):
    scan_res = alpha_admin_client.post(Scans.LIST)
    scan_id = scan_res.json()["scan_id"]

    beta_poll_res = beta_admin_client.get(Scans.status(scan_id))
    assert beta_poll_res.status_code == HTTPStatus.NOT_FOUND


@allure.title("Report summary is scoped to the requesting org")
@allure.epic("Multi-tenancy")
@allure.feature("Data Isolation")
@allure.story("GET /reports/summary")
@allure.tag("positive")
def test_report_summary_is_org_scoped(alpha_admin_client):
    alpha_report = alpha_admin_client.get(Reports.SUMMARY)

    assert alpha_report.status_code == HTTPStatus.OK
    assert alpha_report.json()["org_id"] == USERS["alpha_admin"]["org"]

    # org-beta has 0 findings here, which hits a separate bug (test_reports.py::test_report_summary_for_org_with_no_findings).
