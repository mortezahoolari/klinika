"""
End-to-end Playwright test for the Klinika web app at http://localhost:9000.

Tests:
1. Default language (EN) — page loads with English text
2. Language toggle to DE — German tagline appears
3. EN briefing — Daily Briefing tab content in English
4. DE briefing — German briefing headers after language switch + refresh
5. Chat in EN — English response to a German patient question
"""

import json
import time
import sys
import urllib.error
import urllib.request
from playwright.sync_api import sync_playwright, Page

# Ensure emoji and non-ASCII chars in page text don't crash on Windows terminals
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://localhost:9000"
SCREENSHOT_DIR = "C:/Code/klinika/data"


def screenshot(page: Page, name: str) -> str:
    path = f"{SCREENSHOT_DIR}/{name}.png"
    page.screenshot(path=path)
    print(f"  [Screenshot] Saved: {path}")
    return path


def separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def get_briefing_content(page: Page) -> str:
    """Extract just the briefing content div text."""
    try:
        el = page.locator("#briefing-content")
        if el.count() > 0:
            return el.inner_text()
    except Exception:
        pass
    return ""


def run_tests():
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        # ----------------------------------------------------------------
        # TEST 1: Default language is EN
        # ----------------------------------------------------------------
        separator("TEST 1: Default language is EN")
        page.goto(BASE_URL, wait_until="domcontentloaded")
        # Wait for JS to run and apply language strings
        page.wait_for_timeout(2500)
        screenshot(page, "01_initial_page_load")

        body_text = page.inner_text("body")
        body_upper = body_text.upper()

        # Check tagline
        has_practice_assistant = "Practice Assistant" in body_text
        print(f"  'Practice Assistant' tagline: {'PASS' if has_practice_assistant else 'FAIL'}")

        # Check Daily Briefing tab
        has_daily_briefing_tab = "Daily Briefing" in body_text
        print(f"  'Daily Briefing' tab: {'PASS' if has_daily_briefing_tab else 'FAIL'}")

        # Check Today's Appointments header — CSS uppercases it, so check case-insensitively
        has_appointments_header = (
            "TODAY'S APPOINTMENTS" in body_upper
            or "Today's Appointments" in body_text
        )
        print(f"  \"Today's Appointments\" header: {'PASS' if has_appointments_header else 'FAIL'}")
        print(f"  (body preview: {body_text[:200]!r})")

        test1_pass = has_practice_assistant and has_daily_briefing_tab and has_appointments_header
        results.append(("TEST 1: Default language EN", test1_pass,
                         f"Practice Assistant={has_practice_assistant}, "
                         f"Daily Briefing tab={has_daily_briefing_tab}, "
                         f"Today's Appointments={has_appointments_header}"))
        print(f"\n  => TEST 1: {'PASS' if test1_pass else 'FAIL'}")

        # ----------------------------------------------------------------
        # TEST 2: Language toggle to DE
        # ----------------------------------------------------------------
        separator("TEST 2: Language toggle to DE")

        de_button = page.locator("button", has_text="DE").first
        de_button.click()
        page.wait_for_timeout(1500)
        screenshot(page, "02_after_de_toggle")

        body_text_de = page.inner_text("body")
        has_praxis_assistent = "Praxis-Assistent" in body_text_de
        print(f"  'Praxis-Assistent' tagline: {'PASS' if has_praxis_assistent else 'FAIL'}")
        print(f"  (body preview: {body_text_de[:200]!r})")

        results.append(("TEST 2: Language toggle DE", has_praxis_assistent,
                         f"Praxis-Assistent={has_praxis_assistent}"))
        print(f"\n  => TEST 2: {'PASS' if has_praxis_assistent else 'FAIL'}")

        # ----------------------------------------------------------------
        # TEST 3: EN briefing — switch back to EN then go to Daily Briefing
        # ----------------------------------------------------------------
        separator("TEST 3: EN briefing content")

        # Switch back to EN first
        en_button = page.locator("button", has_text="EN").first
        en_button.click()
        page.wait_for_timeout(1500)

        # Click Daily Briefing tab
        page.get_by_text("Daily Briefing").first.click()
        page.wait_for_timeout(1000)
        screenshot(page, "03_en_briefing_tab_clicked")

        # Wait up to 90 seconds for briefing to load with actual markdown content
        print("  Waiting up to 90 seconds for EN briefing content to load...")
        start = time.time()
        briefing_text = ""
        en_headers_found = []

        while time.time() - start < 90:
            briefing_text = get_briefing_content(page)
            elapsed = time.time() - start

            # Check for EN section headers in markdown output
            en_headers = ["Schedule", "Patient Cards", "Daily Briefing", "Lab Alerts", "Priority",
                          "Summary", "Appointments", "Lab Results"]
            # Also check for loading state
            is_loading = (
                "Generating briefing" in briefing_text
                or "loading" in briefing_text.lower()
                or "..." in briefing_text
                or len(briefing_text.strip()) < 50
            )

            found = [h for h in en_headers if h in briefing_text]
            if found and not is_loading:
                en_headers_found = found
                break

            if int(elapsed) % 10 == 0 and elapsed > 1:
                print(f"    [{elapsed:.0f}s] briefing_text preview: {briefing_text[:80]!r}")

            page.wait_for_timeout(2000)

        screenshot(page, "03_en_briefing_loaded")

        # Check German headers should NOT appear
        de_headers_found = [h for h in ["Terminplan", "Patientenkarten", "Tagesbriefing", "Laborwerte"]
                            if h in briefing_text]

        print(f"  EN headers found: {en_headers_found}")
        print(f"  DE headers found (should be empty): {de_headers_found}")
        print(f"  Briefing content snippet:\n    {briefing_text[:600]!r}")

        test3_pass = len(en_headers_found) > 0 and len(de_headers_found) == 0
        results.append(("TEST 3: EN briefing headers", test3_pass,
                         f"EN headers={en_headers_found}, DE headers={de_headers_found}"))
        print(f"\n  => TEST 3: {'PASS' if test3_pass else 'FAIL'}")

        # ----------------------------------------------------------------
        # TEST 4: DE briefing
        # ----------------------------------------------------------------
        separator("TEST 4: DE briefing content")

        # Switch to DE
        de_button = page.locator("button", has_text="DE").first
        de_button.click()
        page.wait_for_timeout(1500)
        screenshot(page, "04_de_mode_before_briefing")

        # Make sure we're on the Tagesbriefing tab
        for selector in ["text=Tagesbriefing", "text=Daily Briefing"]:
            try:
                loc = page.locator(selector).first
                if loc.count() > 0:
                    loc.click()
                    page.wait_for_timeout(500)
                    break
            except Exception:
                pass

        # Click Refresh/Aktualisieren button
        refresh_clicked = False
        for selector in ["button:has-text('Aktualisieren')", "button:has-text('Refresh')"]:
            try:
                loc = page.locator(selector).first
                if loc.count() > 0:
                    print(f"  Clicking: {selector}")
                    loc.click()
                    refresh_clicked = True
                    page.wait_for_timeout(500)
                    break
            except Exception:
                pass

        if not refresh_clicked:
            print("  WARNING: Could not find refresh button")

        screenshot(page, "04_de_briefing_refresh_clicked")

        # Wait up to 90 seconds for German briefing content
        print("  Waiting up to 90 seconds for DE briefing content...")
        start = time.time()
        de_briefing_text = ""
        de_headers_found2 = []

        while time.time() - start < 90:
            de_briefing_text = get_briefing_content(page)
            elapsed = time.time() - start

            de_headers = ["Terminplan", "Patientenkarten", "Tagesbriefing", "Laborwerte",
                          "Prioritäten", "Zusammenfassung", "Laborbefunde"]
            is_loading = (
                "Briefing wird generiert" in de_briefing_text
                or "loading" in de_briefing_text.lower()
                or len(de_briefing_text.strip()) < 50
            )

            found = [h for h in de_headers if h in de_briefing_text]
            if found and not is_loading:
                de_headers_found2 = found
                break

            if int(elapsed) % 10 == 0 and elapsed > 1:
                print(f"    [{elapsed:.0f}s] briefing_text preview: {de_briefing_text[:80]!r}")

            page.wait_for_timeout(2000)

        screenshot(page, "04_de_briefing_loaded")

        en_headers_found2 = [h for h in ["Schedule", "Patient Cards"] if h in de_briefing_text]

        print(f"  German headers found: {de_headers_found2}")
        print(f"  English headers found (should be empty or minimal): {en_headers_found2}")
        print(f"  Briefing content snippet:\n    {de_briefing_text[:600]!r}")

        test4_pass = len(de_headers_found2) > 0
        results.append(("TEST 4: DE briefing headers", test4_pass,
                         f"DE headers={de_headers_found2}, EN headers={en_headers_found2}"))
        print(f"\n  => TEST 4: {'PASS' if test4_pass else 'FAIL'}")

        # ----------------------------------------------------------------
        # TEST 5: Chat in EN
        # ----------------------------------------------------------------
        separator("TEST 5: Chat in EN — English response")

        # Switch back to EN
        en_button = page.locator("button", has_text="EN").first
        en_button.click()
        page.wait_for_timeout(1500)

        # Navigate to Chat tab
        for selector in ["text=Chat", "button:has-text('Chat')", "#tab-chat"]:
            try:
                loc = page.locator(selector).first
                if loc.count() > 0:
                    loc.click()
                    page.wait_for_timeout(500)
                    break
            except Exception:
                pass

        screenshot(page, "05_chat_tab_en")

        # Count existing messages
        initial_msg_count = page.locator(".message").count()
        print(f"  Initial message count: {initial_msg_count}")

        # Find chat input
        chat_input = page.locator("input[type='text'], textarea").first
        if chat_input.count() == 0:
            print("  ERROR: Could not find chat input!")
            results.append(("TEST 5: Chat EN response", False, "Could not find chat input"))
        else:
            question = "What medications does Karl Schmidt take?"
            chat_input.click()
            chat_input.fill(question)
            screenshot(page, "05_chat_question_typed")
            print(f"  Typed: {question!r}")

            # Submit via button or Enter
            submitted = False
            for selector in ["button:has-text('Send')", "button[type='submit']", "#btn-send"]:
                try:
                    loc = page.locator(selector).first
                    if loc.count() > 0:
                        loc.click()
                        submitted = True
                        print(f"  Submitted via: {selector}")
                        break
                except Exception:
                    pass

            if not submitted:
                chat_input.press("Enter")
                print("  Submitted via Enter")

            screenshot(page, "05_chat_submitted")

            # Wait up to 60 seconds for streaming response to appear and complete
            print("  Waiting up to 60 seconds for chat response...")
            start = time.time()
            assistant_text = ""
            response_received = False

            while time.time() - start < 60:
                elapsed = time.time() - start

                # Count all messages (user + assistant)
                current_msg_count = page.locator(".message").count()

                # Check if streaming div exists (still in progress)
                streaming_count = page.locator(".message.assistant.streaming").count()

                # Check if thinking indicator is visible
                thinking_count = page.locator("#thinking-indicator").count()

                if current_msg_count > initial_msg_count:
                    # New messages appeared — check if still streaming
                    if streaming_count == 0 and thinking_count == 0:
                        # Collect all assistant messages
                        msgs = page.locator(".message.assistant").all()
                        if len(msgs) > 1:  # More than just welcome message
                            assistant_text = msgs[-1].inner_text()
                            response_received = True
                            print(f"  Response received after {elapsed:.0f}s")
                            break
                        elif len(msgs) == 1:
                            # Only welcome message — might still be streaming
                            pass

                if int(elapsed) % 10 == 0 and elapsed > 1:
                    print(f"    [{elapsed:.0f}s] msgs={current_msg_count}, streaming={streaming_count}, thinking={thinking_count}")

                page.wait_for_timeout(2000)

            screenshot(page, "05_chat_response")

            # Final check — get all assistant messages regardless
            all_assistant_msgs = page.locator(".message.assistant").all()
            print(f"  Total assistant messages found: {len(all_assistant_msgs)}")
            for i, m in enumerate(all_assistant_msgs):
                txt = m.inner_text()
                print(f"    msg[{i}]: {txt[:150]!r}")
                if i == len(all_assistant_msgs) - 1:
                    assistant_text = txt

            # Evaluate the response
            if not response_received and len(all_assistant_msgs) <= 1:
                print("  WARNING: No new response appeared within 60 seconds")
                results.append(("TEST 5: Chat EN response", False,
                                 "No response received within 60 seconds"))
            else:
                # Check language of the response
                german_indicators = ["nimmt", "verschrieben", "täglich", "Medikamente nehmen",
                                     "Er nimmt", "er nimmt", "eingenommen", "Patienten"]
                english_indicators = ["takes", "medication", "medications", "prescribed",
                                      "is taking", "is on", "currently on", "Karl Schmidt"]

                de_count = sum(1 for w in german_indicators if w in assistant_text)
                en_count = sum(1 for w in english_indicators if w.lower() in assistant_text.lower())

                print(f"  Response text: {assistant_text[:400]!r}")
                print(f"  German indicators in response: {de_count} ({[w for w in german_indicators if w in assistant_text]})")
                print(f"  English indicators in response: {en_count} ({[w for w in english_indicators if w.lower() in assistant_text.lower()]})")

                # Pass if: has English content OR is not German (no German indicators)
                test5_pass = en_count > 0 or de_count == 0
                # But fail if clearly German
                if de_count > en_count and de_count > 2:
                    test5_pass = False

                results.append(("TEST 5: Chat EN response", test5_pass,
                                 f"EN indicators={en_count}, DE indicators={de_count}, "
                                 f"response={assistant_text[:200]!r}"))
                print(f"\n  => TEST 5: {'PASS' if test5_pass else 'FAIL'}")

        browser.close()

    # ----------------------------------------------------------------
    # TEST 6: /bridges/status endpoint (HTTP, no browser needed)
    # ----------------------------------------------------------------
    separator("TEST 6: GET /bridges/status — JSON structure")

    try:
        with urllib.request.urlopen(f"{BASE_URL}/bridges/status", timeout=5) as resp:
            status_code = resp.status
            body = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        status_code = e.code
        body = {}
    except Exception as exc:
        print(f"  ERROR connecting to {BASE_URL}/bridges/status: {exc}")
        results.append(("TEST 6: /bridges/status", False, str(exc)))
        body = None
        status_code = 0

    if body is not None:
        http_ok = status_code == 200
        has_gdt = isinstance(body.get("gdt"), dict) and "running" in body["gdt"]
        has_ldt = isinstance(body.get("ldt"), dict) and "running" in body["ldt"]
        test6_pass = http_ok and has_gdt and has_ldt

        print(f"  HTTP 200:          {'PASS' if http_ok else 'FAIL'} (got {status_code})")
        print(f"  gdt.running key:   {'PASS' if has_gdt else 'FAIL'}")
        print(f"  ldt.running key:   {'PASS' if has_ldt else 'FAIL'}")
        print(f"  Full response:     {body}")

        results.append((
            "TEST 6: /bridges/status",
            test6_pass,
            f"status={status_code}, gdt={body.get('gdt')}, ldt={body.get('ldt')}",
        ))
        print(f"\n  => TEST 6: {'PASS' if test6_pass else 'FAIL'}")

    # ----------------------------------------------------------------
    # Final summary
    # ----------------------------------------------------------------
    separator("FINAL RESULTS SUMMARY")
    all_pass = True
    for name, passed, detail in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        print(f"         {detail}")
        if not passed:
            all_pass = False

    print(f"\n  Overall: {'ALL TESTS PASSED' if all_pass else 'SOME TESTS FAILED'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(run_tests())
