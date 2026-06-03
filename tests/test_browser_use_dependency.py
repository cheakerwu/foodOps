"""Tests verifying that browser-use package is importable when installed."""

import pytest


@pytest.mark.browser_use
def test_browser_use_imports_are_available():
    from browser_use import Agent, Browser, ChatBrowserUse

    assert Agent is not None
    assert Browser is not None
    assert ChatBrowserUse is not None
