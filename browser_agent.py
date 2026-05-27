"""
UpsideOnly Browser Agent — Ghost Mode
Uses Camoufox (hardened Firefox) to bypass Google bot detection.
Same engine as GhostPrime — invisible to anti-bot systems.
"""

import asyncio
import os
import requests
from camoufox.async_api import AsyncCamoufox

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8776802338:AAENyG3ADwNRpk59CuBDnsh8fDGcEuUFVSg")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7135054241")
GOOGLE_EMAIL = os.getenv("GOOGLE_EMAIL", "kevinleestites2@gmail.com")
GOOGLE_PASSWORD = os.getenv("GOOGLE_PASSWORD", "")

def telegram(msg: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": f"👻 Ghost\n{msg}"},
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
    path = f"/tmp/snap_{label}.png"
    await page.screenshot(path=path)
    telegram_photo(path, f"📸 {label} | {page.url[:60]}")

async def main():
    telegram("👻 Ghost Mode — Camoufox engaging...")
    captured_tokens = []

    async with AsyncCamoufox(headless=True, geoip=True) as browser:
        page = await browser.new_page()

        # Intercept Bearer tokens
        async def handle_request(request):
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer ") and len(auth) > 20:
                token = auth[7:]
                if token not in captured_tokens:
                    captured_tokens.append(token)
                    telegram(f"🔑 TOKEN CAPTURED:\n{token[:120]}")

        page.on("request", handle_request)

        # Navigate to UpsideOnly
        await page.goto("https://upsideonly.com", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        # Check localStorage
        token_check = await page.evaluate("""
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

        if token_check:
            telegram(f"✅ Token in localStorage!")
            with open("token.txt", "w") as f:
                f.write(token_check)
            return

        await snap(page, "01_homepage")

        # Find and click login
        login_clicked = False
        for sel in ["text=Sign in", "text=Log in", "text=Login", "button:has-text('Sign')", "a[href*='login']"]:
            try:
                await page.click(sel, timeout=2000)
                login_clicked = True
                print(f"Login clicked: {sel}")
                break
            except:
                pass

        if not login_clicked:
            await page.goto("https://upsideonly.com/login", wait_until="networkidle", timeout=15000)

        await asyncio.sleep(2)
        await snap(page, "02_login_page")

        # Click Google
        google_clicked = False
        for sel in ["text=Continue with Google", "text=Sign in with Google", "text=Google", "button:has-text('Google')", "[class*='google']"]:
            try:
                await page.click(sel, timeout=2000)
                google_clicked = True
                print(f"Google clicked: {sel}")
                break
            except:
                pass

        if not google_clicked:
            # Direct Auth0 Google connection URL
            auth_url = (
                "https://auth.upsideonly.com/authorize"
                "?response_type=code"
                "&client_id=EH8iKT1Zurk62Xq3gYLD3fkvUm3LRRJH"
                "&redirect_uri=https%3A%2F%2Fupsideonly.com"
                "&scope=openid%20profile%20email%20offline_access"
                "&connection=google-oauth2"
                f"&login_hint={GOOGLE_EMAIL}"
            )
            await page.goto(auth_url, wait_until="networkidle", timeout=20000)

        # Wait for navigation to Google — may open new tab or redirect
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
        except:
            pass

        # If Google opened a new tab, switch to it
        pages = page.context.pages
        if len(pages) > 1:
            page = pages[-1]
            await page.wait_for_load_state("domcontentloaded", timeout=10000)
            telegram(f"📑 Switched to new tab: {page.url[:80]}")

        await asyncio.sleep(3)
        await snap(page, "03_google_page")

        # Enter Google credentials
        try:
            email_input = await page.wait_for_selector("input[type='email']", timeout=12000)
            await email_input.fill(GOOGLE_EMAIL)
            await asyncio.sleep(1)
            await page.keyboard.press("Enter")
            await asyncio.sleep(3)
            await snap(page, "04_after_email")

            if GOOGLE_PASSWORD:
                password_input = await page.wait_for_selector("input[type='password']", timeout=12000)
                await password_input.fill(GOOGLE_PASSWORD)
                await asyncio.sleep(1)
                await page.keyboard.press("Enter")
                await asyncio.sleep(5)
                await snap(page, "05_after_password")
                telegram("🔑 Credentials submitted!")
        except Exception as e:
            await snap(page, "error_state")
            telegram(f"⚠️ Login error: {e}")

        # Final localStorage check
        await asyncio.sleep(4)
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

        token = final_token or (captured_tokens[0] if captured_tokens else None)

        if token:
            with open("token.txt", "w") as f:
                f.write(token)
            telegram(f"🏆 TOKEN ACQUIRED!\n{token[:120]}")
            print(f"TOKEN: {token[:80]}...")
        else:
            await snap(page, "final_state")
            telegram("❌ No token captured")

if __name__ == "__main__":
    asyncio.run(main())
