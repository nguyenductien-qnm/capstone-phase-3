from playwright.sync_api import sync_playwright
import time

def test_frontend():
    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: console_logs.append(f"[ERROR] {err}"))
        
        print("Navigating to http://localhost:8080 ...")
        try:
            page.goto('http://localhost:8080', wait_until='load', timeout=15000)
        except Exception as e:
            print(f"Failed to navigate: {e}")
            browser.close()
            return
            
        # Navigate if needed
        go_shopping = page.get_by_text("Go Shopping")
        if go_shopping.count() > 0:
            print("Clicking 'Go Shopping'...")
            go_shopping.first.click()
            page.wait_for_timeout(2000)
        
        # Take a screenshot of the home page
        page.screenshot(path='/home/dinh/capstone-phase-3/docs/ai/evals/evidence/ui_home.png', full_page=True)
        print("Saved home page screenshot to docs/ai/evals/evidence/ui_home.png")
        
        # Click the chat toggle button
        print("Opening AI Copilot...")
        page.evaluate("Array.from(document.querySelectorAll('button')).forEach(b => { if (b.innerHTML.includes('M20 2H4C2.9')) b.click() })")
        page.wait_for_timeout(2000)
        
        page.screenshot(path='/home/dinh/capstone-phase-3/docs/ai/evals/evidence/ui_ai_open.png')
        print("Saved AI panel open screenshot to docs/ai/evals/evidence/ui_ai_open.png")
        
        # Send a message
        print("Sending a message to AI Copilot...")
        input_selector = 'input[placeholder="Ask about products, sizes, or shipping..."]'
        if page.locator(input_selector).count() > 0:
            page.fill(input_selector, "Xin chào, mình đang tìm một ống nhòm tốt")
            page.press(input_selector, 'Enter')
            print("Message sent, waiting for AI response (this may take up to 15s)...")
            # Wait for response (a new bubble)
            page.wait_for_timeout(15000)
            page.screenshot(path='/home/dinh/capstone-phase-3/docs/ai/evals/evidence/ui_ai_chat.png')
            print("Saved AI chat response screenshot to docs/ai/evals/evidence/ui_ai_chat.png")
        else:
            print("Could not find the chat input box.")

        print("\n=== Console Logs ===")
        if not console_logs:
            print("No console logs or errors found. (Clean!)")
        else:
            for log in console_logs:
                print(log)
        print("====================")
            
        browser.close()

if __name__ == "__main__":
    test_frontend()
