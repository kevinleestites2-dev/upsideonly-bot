"""
OAuth callback server — runs in GitHub Actions
Starts ngrok tunnel, sends login URL to Telegram, waits for callback,
exchanges code for token, saves to GitHub secret, reports to Telegram.
"""
import os, json, time, subprocess, threading, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

TG_TOKEN = os.environ["TELEGRAM_TOKEN"]
TG_CHAT = os.environ["TELEGRAM_CHAT_ID"]
GH_TOKEN = os.environ["GH_TOKEN"]
GH_REPO = os.environ["GH_REPO"]
NGROK_AUTH = os.environ["NGROK_AUTH"]

AUTH0_DOMAIN = "auth.upsideonly.com"
CLIENT_ID = "EH8iKT1Zurk62Xq3gYLD3fkvUm3LRRJH"
AUDIENCE = "https://api.upsideonly.com"
PORT = 8765

captured = {}


def send_tg(msg):
    requests.post(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        json={"chat_id": TG_CHAT, "text": msg, "parse_mode": "HTML"},
        timeout=5
    )


def save_gh_secret(name, value):
    # Get repo public key for secret encryption
    r = requests.get(
        f"https://api.github.com/repos/{GH_REPO}/actions/secrets/public-key",
        headers={"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github+json"}
    )
    key_data = r.json()
    key_id = key_data["key_id"]
    key_b64 = key_data["key"]

    # Encrypt with libsodium
    from base64 import b64encode, b64decode
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
    import struct

    # Use nacl if available, else fallback
    try:
        from nacl.public import PublicKey, SealedBox
        pub_key = PublicKey(b64decode(key_b64))
        box = SealedBox(pub_key)
        encrypted = b64encode(box.encrypt(value.encode())).decode()
    except ImportError:
        # Install PyNaCl inline
        subprocess.run(["pip", "install", "PyNaCl", "-q"], check=True)
        from nacl.public import PublicKey, SealedBox
        pub_key = PublicKey(b64decode(key_b64))
        box = SealedBox(pub_key)
        encrypted = b64encode(box.encrypt(value.encode())).decode()

    r2 = requests.put(
        f"https://api.github.com/repos/{GH_REPO}/actions/secrets/{name}",
        headers={"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github+json"},
        json={"encrypted_value": encrypted, "key_id": key_id}
    )
    return r2.status_code


class CallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress logs

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/callback":
            code = params.get("code", [None])[0]
            error = params.get("error", [None])[0]

            if error:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"<html><body>Auth failed. Close this tab.</body></html>")
                captured["error"] = error
                return

            if code:
                # Exchange code for tokens
                r = requests.post(
                    f"https://{AUTH0_DOMAIN}/oauth/token",
                    json={
                        "grant_type": "authorization_code",
                        "client_id": CLIENT_ID,
                        "code": code,
                        "redirect_uri": f"https://cycling-everyday-unbundle.ngrok-free.dev/callback",
                        "audience": AUDIENCE,
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=15
                )
                tokens = r.json()
                access_token = tokens.get("access_token", "")
                refresh_token = tokens.get("refresh_token", "")

                if access_token:
                    captured["access_token"] = access_token
                    captured["refresh_token"] = refresh_token
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"<html><body style='background:#0a0a0a;color:#00ff88;font-family:monospace;padding:2rem'><h2>SUCCESS — Token Captured</h2><p>Bot is now active. Close this tab.</p></body></html>")
                else:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(f"<html><body>Token exchange failed: {tokens}</body></html>".encode())
                    captured["error"] = str(tokens)
        else:
            self.send_response(404)
            self.end_headers()


def start_ngrok():
    # Use static domain
    proc = subprocess.Popen(
        ["ngrok", "http", f"--domain=cycling-everyday-unbundle.ngrok-free.dev", str(PORT)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    time.sleep(4)
    return proc


def main():
    # Start ngrok
    print("Starting ngrok...")
    ngrok_proc = start_ngrok()
    public_url = "https://cycling-everyday-unbundle.ngrok-free.dev"
    print(f"Tunnel: {public_url}")

    # Build login URL
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": f"{public_url}/callback",
        "scope": "openid profile email offline_access",
        "audience": AUDIENCE,
        "connection": "google-oauth2",
        "login_hint": "kevinleestites2@gmail.com",
    }
    login_url = f"https://{AUTH0_DOMAIN}/authorize?" + urllib.parse.urlencode(params)

    send_tg(
        f"<b>UpsideOnly — Login Ready</b>\n\n"
        f"Open this URL in your phone browser:\n\n"
        f"{login_url}\n\n"
        f"Log in with Google. Token captured automatically.\n"
        f"Window: 5 minutes."
    )
    print(f"Login URL sent to Telegram")

    # Start HTTP server
    server = HTTPServer(("0.0.0.0", PORT), CallbackHandler)
    server.timeout = 1

    deadline = time.time() + 300  # 5 min
    while time.time() < deadline:
        server.handle_request()
        if "access_token" in captured or "error" in captured:
            break

    ngrok_proc.terminate()

    if "access_token" in captured:
        access_token = captured["access_token"]
        refresh_token = captured.get("refresh_token", "")

        print(f"Token captured! Length: {len(access_token)}")

        # Save to GitHub secrets
        status1 = save_gh_secret("UPSIDEONLY_TOKEN", access_token)
        print(f"Saved UPSIDEONLY_TOKEN: {status1}")

        if refresh_token:
            status2 = save_gh_secret("UPSIDEONLY_REFRESH_TOKEN", refresh_token)
            print(f"Saved UPSIDEONLY_REFRESH_TOKEN: {status2}")

        refresh_info = "Refresh token: YES (auto-renewal enabled)" if refresh_token else "Refresh token: NO"
        send_tg(
            f"<b>Token Saved to GitHub Secrets</b>\n\n"
            f"UPSIDEONLY_TOKEN: saved ({status1})\n"
            f"{refresh_info}\n\n"
            f"Bot execution active on next cycle."
        )
    elif "error" in captured:
        send_tg(f"OAuth failed: {captured['error']}")
        print(f"Error: {captured['error']}")
    else:
        send_tg("Timeout — no login received within 5 minutes.")
        print("Timeout")


if __name__ == "__main__":
    main()
