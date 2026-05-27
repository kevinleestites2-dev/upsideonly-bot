"""
UpsideOnly Browser Agent — Pantheon Strike Engine
Uses browser-use to control a real Chromium instance.
Logs into UpsideOnly via Google, extracts token, executes trades.
"""

import asyncio
import os
import json
import requests
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from browser_use import Agent, Browser, BrowserConfig

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8776802338:AAENyG3ADwNRpk59CuBDnsh8fDGcEuUFVSg")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7135054241")
GOOGLE_EMAIL = os.getenv("GOOGLE_EMAIL", "kevinleestites2@gmail.com")

def telegram(msg: str):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": f"🤖 UpsideOnly\n{msg}", "parse_mode": "Markdown"},
            timeout=10
        )
    except Exception as e:
        print(f"Telegram error: {e}")

async def login_and_get_token() -> dict:
    """
    Launch real Chromium, log into UpsideOnly via Google OAuth,
    intercept the Bearer token from localStorage.
    Returns {"access_token": "...", "refresh_token": "..."}
    """
    llm = ChatGroq(
        model="llama3-70b-8192",
        api_key=GROQ_API_KEY,
        temperature=0.1
    )

    browser = Browser(
        config=BrowserConfig(
            headless=True,
            extra_chromium_args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ]
        )
    )

    token_result = {}

    task = f"""
    Your job is to log into UpsideOnly and extract the authentication token.

    Steps:
    1. Navigate to https://upsideonly.com
    2. Click the login/sign-in button
    3. When you see the Google login option, click it
    4. Log in with Google account: {GOOGLE_EMAIL}
    5. After successful login, execute this JavaScript in the browser console:
       const keys = Object.keys(localStorage);
       const authKey = keys.find(k => k.includes('auth0') || k.includes('@@auth0'));
       const data = localStorage.getItem(authKey);
       return data;
    6. Also execute: document.cookie
    7. Return the full localStorage auth data as a JSON string.

    Important: After login, look for any key in localStorage that contains 'access_token' or 'id_token'.
    """

    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
    )

    try:
        result = await agent.run()
        token_result["raw"] = str(result)
        telegram(f"✅ Browser agent completed\nResult length: {len(str(result))}")
        return token_result
    except Exception as e:
        telegram(f"❌ Browser agent error: {e}")
        raise
    finally:
        await browser.close()

async def get_token_via_intercept() -> str:
    """
    Alternative: Use Playwright directly to intercept network requests
    and capture the Bearer token from API calls.
    """
    from playwright.async_api import async_playwright

    access_token = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 11; Red Magic 6) AppleWebKit/537.36",
        )

        page = await context.new_page()

        # Intercept all requests to capture Bearer token
        captured_token = []

        async def handle_request(request):
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer ") and "upsideonly" in request.url:
                token = auth_header.replace("Bearer ", "").strip()
                if token not in captured_token:
                    captured_token.append(token)
                    print(f"[TOKEN CAPTURED] {token[:50]}...")
                    telegram(f"🔑 Token captured!\n`{token[:80]}...`")

        page.on("request", handle_request)

        # Navigate to UpsideOnly
        await page.goto("https://upsideonly.com", wait_until="networkidle")

        # Check if already logged in via localStorage
        token_from_storage = await page.evaluate("""
            () => {
                const keys = Object.keys(localStorage);
                for (const key of keys) {
                    try {
                        const val = JSON.parse(localStorage.getItem(key));
                        if (val && val.body && val.body.access_token) {
                            return val.body.access_token;
                        }
                        if (val && val.access_token) {
                            return val.access_token;
                        }
                    } catch(e) {}
                }
                // Also check all raw values
                for (const key of keys) {
                    const val = localStorage.getItem(key);
                    if (val && val.includes('eyJ')) {
                        return val;
                    }
                }
                return null;
            }
        """)

        if token_from_storage:
            print(f"[TOKEN FROM STORAGE] Found!")
            telegram(f"🔑 Token from storage captured!")
            access_token = token_from_storage
        else:
            # Need to trigger Google login flow
            telegram("🔄 Not logged in — triggering Google OAuth...")

            # Navigate directly to Auth0 Google connection
            auth_url = (
                "https://auth.upsideonly.com/authorize"
                "?response_type=code"
                "&client_id=EH8iKT1Zurk62Xq3gYLD3fkvUm3LRRJH"
                "&redirect_uri=https%3A%2F%2Fupsideonly.com"
                "&scope=openid%20profile%20email%20offline_access"
                f"&audience=https%3A%2F%2Fapi.upsideonly.com"
                "&connection=google-oauth2"
                f"&login_hint={GOOGLE_EMAIL}"
            )

            await page.goto(auth_url, wait_until="networkidle")
            # At this point it needs Google credentials — handled via secrets
            # Will need GOOGLE_PASSWORD secret to proceed
            telegram("⚠️ Google login page reached — needs GOOGLE_PASSWORD secret")

        if captured_token:
            access_token = captured_token[0]

        await browser.close()
        return access_token

async def execute_trade(token: str, market_id: str, side: str, amount: float):
    """Execute a trade on UpsideOnly."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Origin": "https://upsideonly.com",
        "Referer": "https://upsideonly.com/",
    }

    payload = {
        "market_id": market_id,
        "side": side,  # "yes" or "no"
        "amount": amount,
        "type": "market"
    }

    r = requests.post(
        "https://upsideonly.com/api/v1/trades",
        headers=headers,
        json=payload,
        timeout=15
    )
    return r.json()

async def get_leaderboard(token: str = None) -> list:
    """Get current leaderboard — public endpoint."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    r = requests.get(
        "https://upsideonly.com/api/v1/leaderboard",
        headers=headers,
        params={"period": "all_time", "limit": 10},
        timeout=15
    )
    return r.json()

async def get_markets(token: str) -> list:
    """Get available markets to trade."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    r = requests.get(
        "https://upsideonly.com/api/v1/markets",
        headers=headers,
        timeout=15
    )
    return r.json()

async def main():
    telegram("⚡ UpsideOnly Browser Agent — INITIALIZING")

    print("Attempting token capture via network intercept...")
    token = await get_token_via_intercept()

    if token:
        telegram(f"✅ Token acquired! Length: {len(token)}")
        print(f"Token: {token[:80]}...")

        # Get leaderboard
        lb = await get_leaderboard(token)
        telegram(f"📊 Leaderboard acquired — {len(lb)} entries")
        print(json.dumps(lb, indent=2))
    else:
        telegram("⚠️ Token not captured — Google login credentials needed")
        print("Need GOOGLE_PASSWORD env var to complete Google OAuth flow")

if __name__ == "__main__":
    asyncio.run(main())
