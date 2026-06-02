def test_playwright_sync_api_is_available():
    from playwright.sync_api import sync_playwright

    assert callable(sync_playwright)
