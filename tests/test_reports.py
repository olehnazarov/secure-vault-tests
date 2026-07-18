from http import HTTPStatus

import allure
import pytest

from api.bugs import xfail_bug
from api.endpoints import Assets, Findings, Reports
from api.models import FindingStatus, Severity
from config import USERS


@allure.title("Report summary reflects asset and finding count changes")
@allure.epic("Reports")
@allure.feature("Summary")
@allure.tag("E2E")
def test_report_summary_reflects_asset_and_finding_changes(
    alpha_admin_client, make_asset_payload, make_finding_payload
):
    """
    One end-to-end test for all 4 summary fields (total assets, total/open findings,
    severity breakdown, risk score) instead of one test per field: create an asset +
    an open CRITICAL finding, then close it, and assert exact deltas at each step.
    """
    before = alpha_admin_client.get(Reports.SUMMARY).json()

    asset = alpha_admin_client.post(Assets.LIST, json=make_asset_payload()).json()
    try:
        finding = alpha_admin_client.post(
            Findings.LIST,
            json=make_finding_payload(asset["id"], severity=Severity.CRITICAL),
        ).json()

        after_create = alpha_admin_client.get(Reports.SUMMARY).json()
        assert after_create["total_assets"] == before["total_assets"] + 1
        assert after_create["total_findings"] == before["total_findings"] + 1
        assert after_create["open_findings"] == before["open_findings"] + 1
        assert (
            after_create["severity_breakdown"][Severity.CRITICAL]
            == before["severity_breakdown"][Severity.CRITICAL] + 1
        )
        assert after_create["risk_score_percent"] == pytest.approx(
            after_create["open_findings"] / after_create["total_findings"] * 100,
            abs=0.1,
        )

        # closing must drop the finding out of open_findings/severity_breakdown but keep total_findings,
        # proving the breakdown counts open findings only (per the "Open findings broken down by severity" rule)
        alpha_admin_client.patch(
            Findings.status(finding["id"]), json={"status": FindingStatus.CLOSED}
        )
        after_close = alpha_admin_client.get(Reports.SUMMARY).json()
        assert after_close["total_findings"] == after_create["total_findings"]
        assert after_close["open_findings"] == after_create["open_findings"] - 1
        assert (
            after_close["severity_breakdown"][Severity.CRITICAL]
            == after_create["severity_breakdown"][Severity.CRITICAL] - 1
        )
        assert after_close["risk_score_percent"] == pytest.approx(
            after_close["open_findings"] / after_close["total_findings"] * 100, abs=0.1
        )
    finally:
        alpha_admin_client.delete(Assets.by_id(asset["id"]))


@allure.title("Report summary response has the expected shape and value ranges")
@allure.epic("Reports")
@allure.feature("Summary")
@allure.tag("positive")
def test_report_summary_shape(alpha_admin_client):
    response = alpha_admin_client.get(Reports.SUMMARY)
    assert response.status_code == HTTPStatus.OK
    body = response.json()

    assert body["org_id"] == USERS["alpha_admin"]["org"]
    assert body["total_assets"] >= 0
    assert body["total_findings"] >= 0
    assert body["open_findings"] <= body["total_findings"]
    assert set(body["severity_breakdown"].keys()) == set(Severity)
    assert 0 <= body["risk_score_percent"] <= 100


@allure.title("Analyst role can read the report summary")
@allure.epic("Reports")
@allure.feature("RBAC")
@allure.tag("positive")
def test_analyst_can_read_report_summary(alpha_analyst_client):
    response = alpha_analyst_client.get(Reports.SUMMARY)
    assert response.status_code == HTTPStatus.OK
    assert response.json()["org_id"] == USERS["alpha_admin"]["org"]


@allure.title("Report summary works for an org with no findings")
@allure.epic("Reports")
@allure.feature("Summary")
@allure.tag("positive")
@xfail_bug(
    4, '/reports/summary returns 500 "division by zero" for org with no findings'
)
def test_report_summary_for_org_with_no_findings(beta_admin_client):
    response = beta_admin_client.get(Reports.SUMMARY)
    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["org_id"] == USERS["beta_admin"]["org"]
