"""SecureVault API route templates, grouped by entity."""


class Health:
    CHECK = "/health"


class Auth:
    LOGIN = "/auth/login"
    REFRESH = "/auth/refresh"
    LOGOUT = "/auth/logout"


class Assets:
    LIST = "/assets"

    @staticmethod
    def by_id(asset_id: str) -> str:
        return f"/assets/{asset_id}"


class Findings:
    LIST = "/findings"

    @staticmethod
    def by_id(finding_id: str) -> str:
        return f"/findings/{finding_id}"

    @staticmethod
    def status(finding_id: str) -> str:
        return f"/findings/{finding_id}/status"


class Scans:
    LIST = "/scans"

    @staticmethod
    def by_id(scan_id: str) -> str:
        return f"/scans/{scan_id}"

    @staticmethod
    def status(scan_id: str) -> str:
        return f"/scans/{scan_id}/status"


class Reports:
    SUMMARY = "/reports/summary"
