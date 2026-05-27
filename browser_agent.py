"""
UpsideOnly Browser Agent — Pantheon Strike Engine
Debug run: screenshot every step to map the actual UI.
"""

import asyncio
import os
import base64
import requests
from playwright.async_api import async_playwright

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8776802338:AAENyG3ADwNRpk59CuBDnsh8fDGcEuUFVSg")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7135054241")
GOOGLE_EMAIL = os.getenv("GOOGLE_EMAIL", "kevinleestites2@gmail.com")
GOOGLE_PASSWORD = os.getenv("GOOGLE_PASSWORD", "")

def telegram(msg: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": f"🤖 UpsideOnly\n{msg}"},
            timeout=10
        )
    except Exception as e:
        print(f"Telegram error: {e}")

def telegram_photo(path: str, caption: str = ""):
    try:
        with open(path, "rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
                files={"photo": f},
                timeout=15
            )
    except Exception as e:
        print(f"Telegram photo error: {e}")

async def snap(page, label: str):
    """Take screenshot, print DOM summary, send to Telegram."""
    path = f"/tmp/snap_{label}.png"
    await page.screenshot(path=path, full_page=False)
    telegram_photo(path, f"📸 {label}")

    # Also dump all visible text + button labels
    content = await page.evaluate("""
        () => {
            const els = document.querySelectorAll('button, a, input, [role="button"]');
            return Array.from(els).map(e => ({
                tag: e.tagName,
                text: e.innerText?.trim().slice(0, 80),
                type: e.getAttribute('type'),
                href: e.getAttribute('href'),
                class: e.className?.slice(0, 60),
            }));
        }
    """)
    summary = "\n".join([f"  [{e['tag']}] {e['text'] or e['type'] or e['href'] or ''}" for e in content[:20]])
    print(f"\n=== {label} ===\nURL: {page.url}\nElements:\n{summary}\n")
    telegram(f"📋 {label}\nURL: {page.url[:80]}\nElements:\n{summary[:600]}")


async def main():
    telegram("🔍 DEBUG RUN — mapping UpsideOnly login UI")
    captured_tokens = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )

        page = await context.new_page()

        # Capture any Bearer token that appears
        async def handle_request(request):
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer ") and len(auth) > 20:
                token = auth[7:]
                if token not in captured_tokens:
                    captured_tokens.append(token)
                    telegram(f"🔑 TOKEN CAPTURED:\n{token[:120]}")

        page.on("request", handle_request)

        # Step 1: Homepage
        await page.goto("https://upsideonly.com", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
        await snap(page, "01_homepage")

        # Check localStorage
        token_check = await page.evaluate("""
            () => {
                const keys = Object.keys(localStorage);
                const result = {};
                for (const key of keys) {
                    result[key] = (localStorage.getItem(key) || '').slice(0, 100);
                }
                return result;
            }
        """)
        if token_check:
            telegram(f"💾 localStorage keys: {list(token_check.keys())}")
            print(f"localStorage: {token_check}")

        if captured_tokens:
            telegram(f"✅ Already authenticated! Token captured.")
            with open("token.txt", "w") as f:
                f.write(captured_tokens[0])
            await browser.close()
            return

        # Step 2: Find login button — try all common patterns
        login_clicked = False
        selectors = [
            "text=Sign in",
            "text=Log in",
            "text=Login",
            "text=Sign In",
            "text=Get Started",
            "[data-testid='login']",
            "[data-testid='signin']",
            "a[href*='login']",
            "a[href*='signin']",
            "button:has-text('Sign')",
            "button:has-text('Log')",
        ]
        for sel in selectors:
            try:
                await page.click(sel, timeout=2000)
                print(f"Clicked: {sel}")
                login_clicked = True
                break
            except:
                pass

        if not login_clicked:
            telegram("⚠️ No login button found — trying /login direct")
            await page.goto("https://upsideonly.com/login", wait_until="networkidle", timeout=15000)

        await asyncio.sleep(2)
        await snap(page, "02_after_login_click")

        # Step 3: Look for Google OAuth button
        google_clicked = False
        google_selectors = [
            "text=Continue with Google",
            "text=Sign in with Google",
            "text=Google",
            "[data-provider='google']",
            "a[href*='google']",
            "button:has-text('Google')",
            "[class*='google']",
            "[class*='Google']",
        ]
        for sel in google_selectors:
            try:
                await page.click(sel, timeout=2000)
                print(f"Clicked Google: {sel}")
                google_clicked = True
                break
            except:
                pass

        if not google_clicked:
            # Try Auth0 direct URL — bypass the UpsideOnly login page entirely
            telegram("⚠️ No Google button found — trying Auth0 direct URL...")
            auth_url = (
                "https://auth.upsideonly.com/authorize"
                "?response_type=code"
                "&client_id=EH8iKT1Zurk62Xq3gYLD3fkvUm3LRRJH"
                "&redirect_uri=https%3A%2F%2Fupsideonly.com"
                "&scope=openid%20profile%20email%20offline_access"
                "&connection=google-oauth2"
                f"&login_hint={GOOGLE_EMAIL}"
                "&prompt=login"
            )
            await page.goto(auth_url, wait_until="networkidle", timeout=20000)

        await asyncio.sleep(3)
        await snap(page, "03_google_oauth_page")

        # Step 4: Enter Google credentials
        try:
            email_input = await page.wait_for_selector("input[type='email']", timeout=10000)
            await email_input.fill(GOOGLE_EMAIL)
            await snap(page, "04_email_filled")
            await page.keyboard.press("Enter")
            await asyncio.sleep(3)

            await snap(page, "05_after_email_submit")

            if GOOGLE_PASSWORD:
                try:
                    password_input = await page.wait_for_selector("input[type='password']", timeout=10000)
                    await password_input.fill(GOOGLE_PASSWORD)
                    await snap(page, "06_password_filled")
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(5)
                    await snap(page, "07_after_password_submit")
                    telegram("🔑 Full credentials submitted!")
                except Exception as e:
                    await snap(page, "06_password_error")
                    telegram(f"⚠️ Password field error: {e}")
            else:
                telegram("❌ GOOGLE_PASSWORD empty!")

        except Exception as e:
            await snap(page, "04_email_error")
            telegram(f"⚠️ Email field error: {e}")

        # Final wait + localStorage check
        await asyncio.sleep(5)
        await snap(page, "08_final_state")

        final_token = await page.evaluate("""
            () => {
                const keys = Object.keys(localStorage);
                for (const key of keys) {
                    try {
                        const val = JSON.parse(localStorage.getItem(key));
                        if (val && val.body && val.body.access_token) return val.body.access_token;
                        if (val && val.access_token) return val.access_token;
                    } catch(e) {}
                    const raw = localStorage.getItem(key);
                    if (raw && raw.startsWith('eyJ')) return raw;
                }
                return null;
            }
        """)

        await browser.close()

        if final_token or captured_tokens:
            token = final_token or captured_tokens[0]
            with open("token.txt", "w") as f:
                f.write(token)
            telegram(f"🏆 TOKEN ACQUIRED!\n{token[:120]}")
        else:
            telegram("❌ No token — screenshots sent above show what the browser saw")

if __name__ == "__main__":
    asyncio.run(main())
