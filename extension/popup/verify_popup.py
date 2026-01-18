from playwright.sync_api import sync_playwright
import os

def test_popup():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        # Inject mocks for chrome API
        page.add_init_script("""
            window.chrome = {
                storage: {
                    local: {
                        get: (keys, cb) => cb({}),
                        remove: () => {}
                    }
                },
                runtime: {
                    onMessage: {
                        addListener: () => {}
                    }
                }
            };
        """)

        cwd = os.getcwd()
        # Adjusted path since the script is now in extension/popup/, but we run it from root likely?
        # If we run from root, cwd is root. The file is in extension/popup/popup.html.
        file_path = f"file://{cwd}/extension/popup/popup.html"
        
        print(f"Navigating to: {file_path}")
        page.goto(file_path)
        
        # Check title
        assert "Fake News Analyzer" in page.title()
        
        # Check dimensions via CSS (computed style)
        body = page.locator("body")
        width = body.evaluate("el => getComputedStyle(el).width")
        height = body.evaluate("el => getComputedStyle(el).height")
        
        print(f"Computed Body Width: {width}, Height: {height}")
        assert width == "400px"
        assert height == "600px"

        # Mock Fetch and Test Interaction
        page.route("http://127.0.0.1:8000/analyze", lambda route: route.fulfill(
            status=200,
            body='{"verdict": "real", "confidence": "95%", "ml_score": "0.98", "ai_score": "0.02", "explanation": "Likely real.", "evidence": []}',
            headers={"Content-Type": "application/json"}
        ))
        
        page.fill("#input-text", "Test claim")
        page.click("#analyze-btn")
        
        try:
            page.wait_for_selector(".verdict.real", timeout=5000)
            print("Verdict found!")
        except:
            page.screenshot(path="popup_debug.png")
            raise
            
        page.screenshot(path="popup_result.png")
        print("Popup screenshot saved.")
        
        browser.close()

if __name__ == "__main__":
    test_popup()
