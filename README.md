# SecureVault API — Automated Tests

Investigated reported data/security issues in SecureVault, then wrote an automated API test
suite covering auth, RBAC, multi-tenancy, and business-rule enforcement. 72 tests, 13 documented
product bugs - including a Blocker-severity cross-org data isolation bug (BOLA/IDOR) affecting
assets and findings.

**Live test report:** [Report](https://olehnazarov.github.io/secure-vault-tests/)

Automated API tests for the SecureVault CSPM service, written against the live
[OpenAPI spec](http://18.215.161.231:8000/openapi.json) ([Swagger UI](http://18.215.161.231:8000/docs)).
Stack: `pytest` + `httpx` + `allure-pytest`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the tests

Run main test suite (except slow and rate-limit):
```bash
pytest
```

Runs the main suite (69 tests, 28 of them `xfail` for known bugs) against the live API.
Results go to `allure-results/`.

To point the suite at a different env, override `SECUREVAULT_BASE_URL`
```bash
SECUREVAULT_BASE_URL=https://staging.example.com:8000 pytest
```

View the report:
```bash
allure serve allure-results
```

### Rate-limit test (run separately)

`test_login_rate_limit` fires 11 rapid logins to check the 10 req/min throttle. Excluded from
the default run since it burns the shared login quota and would 429 other tests. Run alone, with
~1 minute of no other suite activity before and after:

```bash
pytest -m rate_limit
```

### Slow tests (run separately)

`test_scan_completes_and_reflects_in_inventory` and `test_scan_updates_previously_discovered_assets`
each trigger a discovery scan and poll it to `COMPLETED`, which takes a fixed ~60s. Excluded from
the default run to keep it fast:

```bash
pytest -m slow
```

## What's covered

- **Auth**: login (success/invalid credentials/unknown user), refresh flow, logout, no/invalid
  token, rate limiting.
- **Assets**: CRUD, validation, pagination, RBAC (analyst read/no-create/no-delete), delete-with-open-findings guard.
- **Findings**: creation, status lifecycle, severity immutability, filtering, pagination, RBAC (analyst read/update status).
- **Discovery Scans**: trigger + status polling, polling a non-existent scan, RBAC (analyst read status),
  repeated scans refreshing previously discovered assets.
- **Reports**: summary for an org with data, for an org with zero findings, RBAC (analyst read summary),
  summary fields (asset count, finding counts, severity breakdown, risk score) reflect real data changes.
- **Multi-tenancy**: cross-org isolation for assets, findings, scans, and reports.

## Continuous Integration

Tests run automatically via GitHub Actions on every push to `main` (`.github/workflows/tests.yml`).
The Allure report history is published to [GitHub Pages](https://olehnazarov.github.io/secure-vault-tests/)

## Known product bugs (encoded as `xfail(strict=True)`)

Tracked as GitHub issues: https://github.com/olehnazarov/secure-vault-tests/issues

## Minor spec/implementation discrepancies (not asserted as bugs)

No documented rule is broken, so tests assert the actual behavior instead of `xfail`-ing it. Worth flagging to the API team:

- `POST /assets`, `/findings`, `/scans` return `200`; spec says `201`.
- Successful `DELETE /assets/{id}` returns `200`; spec says `204`.
- Missing/invalid token status codes are inconsistent [Issue](https://github.com/olehnazarov/secure-vault-tests/issues/9)
- The live server closes idle connections faster than `httpx`'s default (5 sec) timeout,
  occasionally causing `RemoteProtocolError`. Fixed client-side via a shorter
  `keepalive_expiry` in `ApiClient`.


## What I couldn't do, and why

### Missing access

- **No `org-beta` analyst account** - only `org-alpha` admin/analyst and `org-beta` admin were
  provided. This means RBAC (role) and multi-tenancy were each fully tested individually,
  but never together in org-beta - I can't confirm analyst restrictions are enforced identically
  across organizations, only that they work in org-alpha specifically. Given a second analyst
  account in any other org.
- **No visibility into recent changes** - no access to commit history, CI/deploy logs, or existing
  test coverage for the service. Investigating blind, without knowing what changed recently or
  what's already known to be untested, means some risk areas may have been under- or over-prioritized.

### Time constraints

- **Contract/schema validation** against `openapi.json` (e.g. `schemathesis`) — would catch drift
  like the 200-vs-201 mismatches automatically instead of by hand.
- **Performance / scale testing** — all coverage here is functional API testing; nothing
  validates behavior under high data volume or concurrent load. Given more time, I'd start with
  `GET /findings` and `/reports/summary`, since filtering and aggregation are the most likely to
  degrade under a large dataset.
- **Input sanitization / injection testing** — not systematically probed. Worth testing
  filter/search parameters for injection specifically, not just malformed input.
- **Discovery Scan accuracy** — tests confirm a scan completes and refreshes existing assets, but
  not whether it discovers the *correct* real AWS resources (no false positives/negatives). Would
  need a controlled AWS test account with known resources.
- **A dedicated rate-limit account/IP** so `test_login_rate_limit` doesn't need to run in isolation.
- **Concurrency tests**: parallel refresh-token reuse, overlapping scans for the same org.
- **Nicer Allure step breakdown**: right now each step is just "API Request: METHOD URL" plus a
  raw request/response log attachment. Wrapping test logic in named `allure.step()` blocks (e.g. "Create asset", 
  "Trigger scan" etc.) would make the report read like the test's actual scenario 
  instead of a flat list of HTTP calls.
- **Hide sensitive data**: `config.py` has plaintext passwords for all test accounts and BASE_URL.
  Good practice would be to move these to a secrets manager or env vars instead of committing them.

### Requires a team decision

- **Asset "ownership" semantics** — a PUT-by-analyst probe returned `403 Not the asset owner`,
  suggesting update rights may be tied to the creator, not just role. Undocumented in the Product
  Overview — worth confirming with the team whether this is intended.
- **Scan-trigger concurrency** — unclear whether unlimited concurrent scans per org is intended
  or a gap; not documented either way.