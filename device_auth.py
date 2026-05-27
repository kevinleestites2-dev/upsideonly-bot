"""
UpsideOnly Device Authorization Flow
No callback URL needed — works on any device
"""
import requests, time, json, os, base64, subprocess

AUTH0_DOMAIN = "auth.upsideonly.com"
CLIENT_ID = "EH8iKT1Zurk62Xq3gYLD3fkvUm3LRRJH"
AUDIENCE = "https://api.upsideonly.com"
TG_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8776802338:AAENyG3ADwNRpk59CuBDnsh8fDGcEuUFVSg")
TG_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "7135054241")


def send_tg(msg):
    requests.post(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        json={"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"},
        timeout=5
    )


def save_gh_secret(name, value):
    GH_TOKEN = os.environ.get("GH_TOKEN", "")
    GH_REPO = os.environ.get("GH_REPO", "kevinleestites2-dev/upsideonly-bot")
    if not GH_TOKEN:
        print(f"No GH_TOKEN — {name}={value[:20]}...")
        return 0

    r = requests.get(
        f"https://api.github.com/repos/{GH_REPO}/actions/secrets/public-key",
        headers={"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github+json"}
    )
    key_data = r.json()
    key_id = key_data["key_id"]
    key_b64 = key_data["key"]

    try:
        from nacl.public import PublicKey, SealedBox
    except ImportError:
        subprocess.run(["pip", "install", "PyNaCl", "-q"], check=True)
        from nacl.public import PublicKey, SealedBox

    pub_key = PublicKey(base64.b64decode(key_b64))
    box = SealedBox(pub_key)
    encrypted = base64.b64encode(box.encrypt(value.encode())).decode()

    r2 = requests.put(
        f"https://api.github.com/repos/{GH_REPO}/actions/secrets/{name}",
        headers={"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github+json"},
        json={"encrypted_value": encrypted, "key_id": key_id}
    )
    return r2.status_code


def main():
    print("Requesting device code...")

    r = requests.post(
        f"https://{AUTH0_DOMAIN}/oauth/device/code",
        json={
            "client_id": CLIENT_ID,
            "audience": AUDIENCE,
            "scope": "openid profile email offline_access"
        },
        headers={"Content-Type": "application/json"},
        timeout=15
    )
    data = r.json()
    print(f"Device code response: {data}")

    if "error" in data:
        send_tg(f"Device auth failed: {data.get('error_description', data['error'])}")
        return

    device_code = data["device_code"]
    user_code = data["user_code"]
    verify_uri = data.get("verification_uri_complete") or data.get("verification_uri")
    expires_in = data.get("expires_in", 300)
    interval = data.get("interval", 5)

    send_tg(
        f"<b>UpsideOnly - One-Tap Login</b>\n\n"
        f"Open this URL in your phone browser:\n\n"
        f"{verify_uri}\n\n"
        f"Log in with Google. Token captured automatically.\n"
        f"Window: {expires_in // 60} minutes."
    )
    print(f"Login URL sent. Code: {user_code}")

    deadline = time.time() + expires_in
    while time.time() < deadline:
        time.sleep(interval)
        r2 = requests.post(
            f"https://{AUTH0_DOMAIN}/oauth/token",
            json={
                "client_id": CLIENT_ID,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
            },
            headers={"Content-Type": "application/json"},
            timeout=15
        )
        tok = r2.json()

        if "access_token" in tok:
            access_token = tok["access_token"]
            refresh_token = tok.get("refresh_token", "")
            print(f"Token captured! Length: {len(access_token)}")

            s1 = save_gh_secret("UPSIDEONLY_TOKEN", access_token)
            if refresh_token:
                save_gh_secret("UPSIDEONLY_REFRESH_TOKEN", refresh_token)

            send_tg(
                f"<b>Token Captured + Saved</b>\n\n"
                f"UPSIDEONLY_TOKEN: saved\n"
                f"Refresh token: {'yes' if refresh_token else 'no'}\n\n"
                f"Bot is now active."
            )
            return

        err = tok.get("error")
        if err == "authorization_pending":
            print("Waiting for login...")
            continue
        elif err == "slow_down":
            interval += 5
            continue
        elif err:
            print(f"Error: {tok}")
            send_tg(f"Token poll error: {tok.get('error_description', err)}")
            return

    send_tg("Timeout - no login within window.")
    print("Timeout")


if __name__ == "__main__":
    main()
