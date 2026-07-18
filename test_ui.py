from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("http://localhost:8080/")
    page.screenshot(path="ui_home.png", full_page=True)
    browser.close()
