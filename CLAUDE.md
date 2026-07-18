# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Project: SecureVault API Tests

API test suite for SecureVault, a live CSPM service at `http://18.215.161.231:8000`. No app code
lives here - tests only, run against the real deployed API (`/openapi.json`). Python 3.14, pytest.

## Setup

- Virtual environment: `source .venv/bin/activate`
- Install deps: `pip install -r requirements.txt`
- Credentials: `config.py::USERS` (org-alpha admin/analyst, org-beta admin)

## Commands

- `pytest` - full suite (excludes `rate_limit`- and `slow`-marked tests)
- `pytest tests/test_assets.py::test_update_asset -v` - single test
- `pytest -m rate_limit` - login-throttle test, run in isolation, not back-to-back with the main suite
- `pytest -m slow` - scan-completion polling test (~60s+), run separately to keep the main suite fast
- `allure serve allure-results` - interactive report
- `allure generate allure-results -o allure-report --clean` - static report

## Project Structure

- `config.py` - `BASE_URL`, `USERS`
- `api/api_client.py` - `httpx.Client` wrapper with `@allure.step` request/response logging; always use this, never raw `httpx.Client`
- `conftest.py` - session-scoped authenticated clients (`alpha_admin_client`, `alpha_analyst_client`, `beta_admin_client`) + factory fixtures (`make_asset_payload`, `make_finding_payload`, `alpha_asset`)
- `tests/` - one file per resource: `test_auth.py`, `test_assets.py`, `test_findings.py`, `test_scans.py`, `test_reports.py`, `test_tenants.py`

## Workflow

- After adding or modifying a test, run it in isolation before running the full suite
- Run `pytest` (full suite) before considering a task complete

## Testing

- Tests create their own throwaway data via the `make_*` factory fixtures - never rely on fixed seed data, the service is shared
- Known API bugs use the `xfail_bug(issue_number, description)` helper (see `api/bugs.py`) -
  combines `@allure.issue` and `@pytest.mark.xfail(strict=True)` with a consistent reason format
- IMPORTANT: Do not "fix" an xfail test by relaxing its assertion to match current (buggy) behavior
- If a test fails unexpectedly (not already marked xfail), check open GitHub Issues first before changing any code - 
  it may be a known bug that needs an `xfail_bug` decorator, or  behavior should be investigated

## Working with GitHub Issues

Tracked bugs live in GitHub Issues (public repo, no auth needed for reads):

```bash
curl -s https://api.github.com/repos/olehnazarov/secure-vault-tests/issues?state=open
```

Extract only `number` and `title` from each issue when reviewing this list, DO NOT dump the full JSON into context

## Good Commit Message Format
- feat: adds a new test or feature
- fix: fixes a test or bug
- refactor: rewrites/restructures the code
- doc: adds/rewrites documentation, readme, comments
- imperative mood 

## Live API quirks

- `POST /assets|/findings|/scans` return `200` (spec says `201`); `DELETE /assets/{id}` returns `200` (spec says `204`); a missing token returns `403` (spec says `401`) - an invalid token correctly returns `401`
- `GET /assets` and `GET /findings` return `{total, page, limit, items}`, not a bare array
- `severity`/`status` filter params on `GET /findings` are case-sensitive despite the documented case-insensitive rule (tracked bug)

## Do NOT

- Do not instantiate `httpx.Client` directly in tests/fixtures - use `api.api_client.ApiClient`
- Do not loosen an `xfail` assertion to match buggy behavior instead of the documented one
- Do not hardcode raw status-code integers - always compare against `http.HTTPStatus` members
  (e.g. `HTTPStatus.OK`, not `200`)
- Do not hardcode repeated domain string literals (finding `severity`/`status` values, etc.) -
  use the shared enums in `api/models.py` (`Severity`, `FindingStatus`)

## Code comments

- Keep comments short, plain, and dry - one line where possible, no more than 2-3 lines for complex logic. 
  State what the code does or why a non-obvious decision was made, nothing more. 
  No restating the obvious, no marketing language, no verbose explanations of standard patterns.