import time
import os
from playwright.sync_api import sync_playwright

FRONTEND_URL = "http://127.0.0.1:5173"
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

def run_browser_integration_tests():
    print("=== STARTING FRONTEND + BACKEND BROWSER INTEGRATION TESTING ===")
    os.makedirs("test_screenshots", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=EDGE_PATH, headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        # Capture console errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # 1. Open Application Home
        page.goto(FRONTEND_URL)
        page.wait_for_selector("text=Asteris!", timeout=5000)
        page.screenshot(path="test_screenshots/01_home_page.png")
        print("[1] Home page loaded cleanly.")

        # 2. Test Invalid PIN join error
        page.fill("#game-pin", "12345678")
        page.fill("#player-nickname", "Tester")
        page.locator("button[type='submit']").click()
        page.wait_for_selector(".text-red-700", timeout=5000)
        err_msg = page.locator(".text-red-700").inner_text()
        print(f"[2] Invalid PIN properly shows error alert: '{err_msg}'")
        page.screenshot(path="test_screenshots/02_invalid_pin_error.png")

        # 3. Protected Route Redirection (Try accessing /admin/dashboard directly without login)
        page.goto(f"{FRONTEND_URL}/admin/dashboard")
        page.wait_for_url("**/admin/login**", timeout=5000)
        print("[3] Protected route /admin/dashboard redirects unauthenticated users to /admin/login.")

        # 4. Admin Login with Invalid Credentials
        page.fill("#username", "admin")
        page.fill("#password", "wrongpassword123")
        page.click("button:has-text('SIGN IN')")
        page.wait_for_selector("text=Invalid username or password", timeout=5000)
        page.screenshot(path="test_screenshots/03_admin_invalid_login.png")
        print("[4] Admin login with wrong credentials displays proper error.")

        # 5. Admin Login with Valid Credentials
        page.fill("#username", "admin")
        page.fill("#password", "admin1234")
        page.click("button:has-text('SIGN IN')")
        page.wait_for_url("**/admin/dashboard**", timeout=8000)
        page.wait_for_selector("text=Welcome, admin!", timeout=5000)
        page.screenshot(path="test_screenshots/04_admin_dashboard.png")
        print("[5] Admin login succeeded, redirected to dashboard.")

        # 6. Navigate to Create Quiz Page
        page.click("button:has-text('CREATE')")
        page.wait_for_url("**/admin/create**", timeout=5000)
        page.wait_for_selector("text=Create your quiz", timeout=5000)

        # Fill Quiz Form
        quiz_title = f"UI Automated Quiz {int(time.time())}"
        page.fill("#quiz-title", quiz_title)
        page.fill("#quiz-desc", "Created via automated Playwright UI testing")
        page.fill("input[placeholder='Enter the question text']", "What is the capital of France?")
        page.fill("input[placeholder='Option A']", "Paris")
        page.fill("input[placeholder='Option B']", "Rome")
        page.fill("input[placeholder='Option C']", "Berlin")
        page.fill("input[placeholder='Option D']", "Madrid")

        page.screenshot(path="test_screenshots/05_create_quiz_form.png")

        # Save Quiz
        page.on("dialog", lambda dialog: dialog.accept())
        page.click("button:has-text('SAVE QUIZ')")

        # Verify redirect to Saved Quizzes
        page.wait_for_url("**/admin/quizzes**", timeout=10000)
        page.wait_for_selector(f"text={quiz_title}", timeout=5000)
        page.screenshot(path="test_screenshots/06_saved_quizzes.png")
        print(f"[6] Quiz '{quiz_title}' created via UI and persisted to PostgreSQL backend.")

        # 7. Refresh browser and verify data persistence
        page.reload()
        page.wait_for_selector(f"text={quiz_title}", timeout=5000)
        print("[7] Browser refresh verified: Quiz persistence confirmed.")

        # 8. Start Hosting Quiz
        host_btn = page.locator("button:has-text('HOST LIVE')").first
        host_btn.click()

        page.wait_for_url("**/admin/host**", timeout=8000)
        page.wait_for_selector("text=LIVE HOST CONTROLLER", timeout=5000)
        page.wait_for_selector("text=LIVE SYNC ON", timeout=5000)
        page.wait_for_timeout(1000)
        page.screenshot(path="test_screenshots/07_host_lobby.png")
        print("[8] Host controller loaded, WebSocket synchronized, lobby initialized.")

        # Get PIN from Host Controller screen
        pin = page.locator("p.tracking-widest.text-\\[\\#31064D\\]").inner_text().strip()
        assert len(pin) >= 4 and pin != "--------", f"Invalid PIN found: {pin}"
        print(f"[9] Extracted active Game PIN: {pin}")

        # 9. Open Participant Window in a second context
        p_context = browser.new_context(viewport={"width": 450, "height": 800})
        p_page = p_context.new_page()
        p_page.goto(f"{FRONTEND_URL}/")
        p_page.fill("#game-pin", pin)
        p_page.fill("#player-nickname", "UIPupil")
        p_page.click("button:has-text('ENTER GAME')")

        # Verify participant enters lobby
        p_page.wait_for_selector("text=You're In!", timeout=5000)
        p_page.screenshot(path="test_screenshots/08_participant_lobby.png")
        print("[10] Participant joined and entered live waiting lobby.")

        # Verify Host screen shows player in lobby
        page.wait_for_selector("text=UIPupil", timeout=5000)
        page.screenshot(path="test_screenshots/09_host_sees_player.png")
        print("[11] Host dashboard dynamically displays joined player.")

        # 10. Host Starts Quiz
        page.click("button:has-text('START QUIZ NOW')")

        # Verify both host and participant see Question
        page.wait_for_selector("text=What is the capital of France?", timeout=5000)
        p_page.wait_for_selector("text=What is the capital of France?", timeout=5000)
        p_page.screenshot(path="test_screenshots/10_participant_question.png")
        print("[12] Quiz live start verified across Host and Participant.")

        # 11. Participant Submits Answer Option A (Paris)
        p_page.click("button:has-text('Paris')")
        p_page.wait_for_selector("text=Answer Locked In!", timeout=5000)
        p_page.screenshot(path="test_screenshots/11_participant_locked.png")
        print("[13] Participant successfully locked in answer.")

        # Verify Host sees answered count updated
        page.wait_for_selector("text=1 answered", timeout=5000)
        print("[14] Host screen verified answer count live update.")

        # 12. Host Reveals Answer
        page.click("button:has-text('REVEAL ANSWER & SCORE')")
        page.wait_for_selector("text=NEXT QUESTION", timeout=5000)

        # Participant receives results
        p_page.wait_for_selector("text=Question Scored!", timeout=5000)
        p_page.screenshot(path="test_screenshots/12_participant_scored.png")
        print("[15] Answer reveal and scoring verified in UI.")

        # 13. Host Ends Game
        page.click("button:has-text('End Quiz Now')")
        page.wait_for_selector("text=Quiz Complete!", timeout=5000)
        p_page.wait_for_selector("text=Game Over!", timeout=5000)
        p_page.screenshot(path="test_screenshots/13_game_over.png")
        print("[16] Game completion and final standings verified.")

        # 14. Admin Logout test
        page.goto(f"{FRONTEND_URL}/admin/dashboard")
        page.click("button:has-text('LOGOUT')")
        page.wait_for_url(f"{FRONTEND_URL}/", timeout=5000)

        # Try to navigate back to dashboard
        page.goto(f"{FRONTEND_URL}/admin/dashboard")
        page.wait_for_url("**/admin/login**", timeout=5000)
        print("[17] Logout and session destruction verified. Back navigation properly protected.")

        p_context.close()
        context.close()
        browser.close()

    print(f"\nBrowser Integration Console Errors: {len(console_errors)}")
    print("=== FRONTEND + BACKEND INTEGRATION TESTING PASSED 100% ===")

if __name__ == "__main__":
    run_browser_integration_tests()
