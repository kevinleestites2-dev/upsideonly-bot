"""
UpsideOnly Browser Agent — Pantheon Strike Engine
Playwright intercepts network requests to capture Bearer token.
Then fires trades autonomously.
"""

import asyncio
import os
import json
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

async def get_token_via_browser() -> str:
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

        async def handle_request(request):
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer ") and len(auth) > 20:
                token = auth[7:]
                if token not in captured_tokens:
                    captured_tokens.append(token)
                    print(f"[TOKEN CAPTURED] {token[:60]}...")

        page.on("request", handle_request)

        telegram("🌐 Browser launched — navigating to UpsideOnly...")
        await page.goto("https://upsideonly.com", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # Check localStorage first
        token_from_storage = await page.evaluate("""
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

        if token_from_storage:
            telegram("✅ Token found in localStorage!")
            await browser.close()
            return token_from_storage

        # Not logged in — trigger Google OAuth
        telegram("🔐 Not logged in — starting Google OAuth...")

        try:
            await page.click("text=Sign in", timeout=5000)
        except:
            try:
                await page.click("text=Log in", timeout=5000)
            except:
                await page.goto("https://upsideonly.com/login", wait_until="domcontentloaded", timeout=15000)

        await asyncio.sleep(2)

        try:
            await page.click("text=Continue with Google", timeout=8000)
        except:
            try:
                await page.click("text=Google", timeout=5000)
            except:
                telegram("⚠️ Could not find Google button")

        await asyncio.sleep(3)
        telegram(f"📍 At: {page.url[:80]}")

        try:
            email_input = await page.wait_for_selector("input[type='email']", timeout=10000)
            await email_input.fill(GOOGLE_EMAIL)
            await page.keyboard.press("Enter")
            await asyncio.sleep(2)

            if GOOGLE_PASSWORD:
                password_input = await page.wait_for_selector("input[type='password']", timeout=10000)
                await password_input.fill(GOOGLE_PASSWORD)
                await page.keyboard.press("Enter")
                await asyncio.sleep(5)
                telegram("🔑 Credentials submitted — waiting for redirect...")
            else:
                telegram("❌ GOOGLE_PASSWORD is empty!")

        except Exception as e:
            telegram(f"❌ Login error: {e}")

        await asyncio.sleep(5)

        # Check localStorage post-login
        token_after = await page.evaluate("""
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

        if token_after:
            telegram("✅ Token captured post-login!")
            return token_after

        if captured_tokens:
            telegram("✅ Token intercepted from network!")
            return captured_tokens[0]

        return None

async def main():
    telegram("⚡ UpsideOnly Browser Strike — FIRING")
    print(f"Password set: {'YES' if GOOGLE_PASSWORD else 'NO'}")

    token = await get_token_via_browser()

    if token:
        with open("token.txt", "w") as f:
            f.write(token)
        print(f"TOKEN: {token[:80]}...")
        telegram(f"🏆 TOKEN ACQUIRED!\n{token[:100]}\n\nBot is fully armed.")
    else:
        telegram("❌ Token not captured — check logs")
        print("No token captured")

if __name__ == "__main__":
    asyncio.run(main())
