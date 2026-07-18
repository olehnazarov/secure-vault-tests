import time
from http import HTTPStatus

import allure
import pytest

from api.endpoints import Assets, Findings, Scans
from api.models import ScanStatus
from config import USERS

NONEXISTENT_ID = "00000000-0000-0000-0000-000000000000"


def wait_for_scan_completion(
    client, scan_id: str, timeout: float = 90, interval: float = 2
) -> dict:
    """Poll scan status until COMPLETED/FAILED or timeout. Raises if the deadline is hit."""
    deadline = time.monotonic() + timeout
    body = None
    while time.monotonic() < deadline:
        response = client.get(Scans.status(scan_id))
        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert body["status"] in set(ScanStatus)
        if body["status"] in (ScanStatus.COMPLETED, ScanStatus.FAILED):
            return body
        time.sleep(interval)
    last = body["status"] if body else None
    raise TimeoutError(f"scan did not complete within {timeout}s, last status: {last}")


@allure.title("Triggering a scan returns an in-progress status")
@allure.epic("Discovery Scans")
@allure.feature("Lifecycle")
@allure.tag("positive")
def test_scan_trigger_returns_in_progress_status(alpha_admin_client):
    """
    Short health check on trigger only, not a lifecycle test
    """
    trigger_res = alpha_admin_client.post(Scans.LIST)
    # openapi.json declares 201 for this route, but the live API actually returns 200.
    assert trigger_res.status_code == HTTPStatus.OK
    body = trigger_res.json()
    assert body["status"] == ScanStatus.IN_PROGRESS
    scan_id = body["scan_id"]

    status_res = alpha_admin_client.get(Scans.status(scan_id))
    assert status_res.status_code == HTTPStatus.OK
    assert status_res.json()["status"] in set(ScanStatus)


@allure.title("Analyst role can read scan status")
@allure.epic("Discovery Scans")
@allure.feature("RBAC")
@allure.tag("positive")
def test_analyst_can_read_scan_status(alpha_admin_client, alpha_analyst_client):
    trigger_res = alpha_admin_client.post(Scans.LIST)
    scan_id = trigger_res.json()["scan_id"]

    status_res = alpha_analyst_client.get(Scans.status(scan_id))
    assert status_res.status_code == HTTPStatus.OK
    assert status_res.json()["status"] in set(ScanStatus)


@allure.title("Analyst role cannot trigger a scan")
@allure.epic("Discovery Scans")
@allure.feature("RBAC")
@allure.tag("negative")
@pytest.mark.xfail(
    reason="https://github.com/olehnazarov/secure-vault-tests/issues/5 - "
    "analyst role can trigger scans via POST /scans (got 200), "
    "Product Overview restricts analyst to read access plus finding status updates only",
    strict=True,
)
def test_analyst_cannot_trigger_scan(alpha_analyst_client):
    response = alpha_analyst_client.post(Scans.LIST)
    assert response.status_code == HTTPStatus.FORBIDDEN


@allure.title("Return 404 when polling a nonexistent scan")
@allure.epic("Discovery Scans")
@allure.feature("Validation")
@allure.tag("negative")
def test_poll_nonexistent_scan_returns_404(alpha_admin_client):
    response = alpha_admin_client.get(Scans.status(NONEXISTENT_ID))
    assert response.status_code == HTTPStatus.NOT_FOUND


@allure.title("Scan refreshes previously discovered assets")
@pytest.mark.slow
@allure.epic("Discovery Scans")
@allure.feature("Lifecycle")
@allure.tag("positive")
def test_scan_updates_previously_discovered_assets(alpha_admin_client):
    """
    Scan re-touches updated_at on existing assets, not just new ones - matched by id
    since org-alpha is a shared pool other tests also mutate concurrently.
    """
    before = {
        a["id"]: a["updated_at"]
        for a in alpha_admin_client.get(Assets.LIST, params={"limit": 100}).json()[
            "items"
        ]
    }

    trigger_res = alpha_admin_client.post(Scans.LIST)
    scan_id = trigger_res.json()["scan_id"]
    wait_for_scan_completion(alpha_admin_client, scan_id)

    after = {
        a["id"]: a["updated_at"]
        for a in alpha_admin_client.get(Assets.LIST, params={"limit": 100}).json()[
            "items"
        ]
    }

    updated_ids = {
        aid for aid, ts in before.items() if aid in after and after[aid] > ts
    }
    assert (
        updated_ids
    ), "expected at least one pre-existing asset to be refreshed by the scan"


@allure.title("Completed scan is reflected in the asset and finding inventory")
@pytest.mark.slow
@allure.epic("Discovery Scans")
@allure.feature("Lifecycle")
@allure.tag("positive")
def test_scan_completes_and_reflects_in_inventory(alpha_admin_client):
    """
    Scan takes a fixed ~60s to complete - excluded from the default run (pytest.ini `slow`)
    Doesn't always add new assets/findings, so only asserts inventory never shrinks
    """
    assets_before = alpha_admin_client.get(Assets.LIST, params={"limit": 1}).json()[
        "total"
    ]
    findings_before = alpha_admin_client.get(Findings.LIST, params={"limit": 1}).json()[
        "total"
    ]

    trigger_res = alpha_admin_client.post(Scans.LIST)
    scan_id = trigger_res.json()["scan_id"]
    scan_body = wait_for_scan_completion(alpha_admin_client, scan_id)

    assert scan_body["org_id"] == USERS["alpha_admin"]["org"]
    assert scan_body["started_at"] is not None
    assert scan_body["completed_at"] is not None
    assert scan_body["completed_at"] > scan_body["started_at"]

    assets_after = alpha_admin_client.get(Assets.LIST, params={"limit": 1}).json()[
        "total"
    ]
    findings_after = alpha_admin_client.get(Findings.LIST, params={"limit": 1}).json()[
        "total"
    ]
    assert assets_after >= assets_before
    assert findings_after >= findings_before
