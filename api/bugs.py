import allure
import pytest


def xfail_bug(issue_number: int, description: str):
    """Combines @allure.issue and @pytest.mark.xfail for a tracked,
    confirmed bug. `description` should explain the bug itself, not
    repeat the issue number or URL."""

    def decorator(func):
        func = allure.issue(str(issue_number))(func)
        func = pytest.mark.xfail(
            reason=f"{description} (see issue #{issue_number})",
            strict=True,
        )(func)
        return func

    return decorator
