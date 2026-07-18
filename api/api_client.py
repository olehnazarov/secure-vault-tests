from http import HTTPMethod

import allure
import httpx

REDACTED_HEADERS = {"authorization", "cookie", "set-cookie"}

# The server silently drops idle keep-alive connections after ~5s; expire pooled
# connections earlier so httpx never reuses a dead one (RemoteProtocolError).
KEEPALIVE_EXPIRY = 4.0


def _redact_headers(headers: httpx.Headers) -> dict:
    return {
        key: ("[REDACTED]" if key.lower() in REDACTED_HEADERS else value)
        for key, value in headers.items()
    }


def _log_combined(request: httpx.Request, response: httpx.Response):
    req_body = (
        request.content.decode("utf-8", errors="replace") if request.content else "{}"
    )
    res_body = response.text if response.content else ""
    log_content = (
        f"=== REQUEST ===\n"
        f"Method: {request.method}\n"
        f"URL: {request.url}\n"
        f"Headers: {_redact_headers(request.headers)}\n"
        f"Body:\n{req_body}\n\n"
        f"=== RESPONSE ===\n"
        f"Status Code: {response.status_code}\n"
        f"Headers: {_redact_headers(response.headers)}\n"
        f"Body:\n{res_body}"
    )
    allure.attach(log_content, name="log", attachment_type=allure.attachment_type.TEXT)


class ApiClient:
    """General HTTP client with Allure logging. Auth tokens and cookies are
    redacted from logged headers - see REDACTED_HEADERS."""

    def __init__(self, base_url: str, headers: dict | None = None):
        self.client = httpx.Client(
            base_url=base_url,
            headers=headers,
            timeout=10.0,
            limits=httpx.Limits(keepalive_expiry=KEEPALIVE_EXPIRY),
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def post(self, url: str, json: dict | None = None, **kwargs) -> httpx.Response:
        return self._request(HTTPMethod.POST, url, json=json, **kwargs)

    def get(self, url: str, params: dict | None = None, **kwargs) -> httpx.Response:
        return self._request(HTTPMethod.GET, url, params=params, **kwargs)

    def put(self, url: str, json: dict | None = None, **kwargs) -> httpx.Response:
        return self._request(HTTPMethod.PUT, url, json=json, **kwargs)

    def delete(self, url: str, **kwargs) -> httpx.Response:
        return self._request(HTTPMethod.DELETE, url, **kwargs)

    def patch(self, url: str, json: dict | None = None, **kwargs) -> httpx.Response:
        return self._request(HTTPMethod.PATCH, url, json=json, **kwargs)

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        # build_request composes the exact wire request (merged client + call
        # headers, full URL with query string, encoded body) so the Allure log
        # reflects what was actually sent, not just the arguments passed in.
        request = self.client.build_request(method, url, **kwargs)
        # Plain step title only - no @allure.step decorator, so call kwargs
        # (json/params) aren't auto-dumped as step parameters; everything
        # goes through custom _log_combined function instead
        with allure.step(f"API Request: {method} {request.url}"):
            response = self.client.send(request)
            _log_combined(request, response)
        return response

    def close(self):
        self.client.close()
