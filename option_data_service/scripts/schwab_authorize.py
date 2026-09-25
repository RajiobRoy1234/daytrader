"""One-time interactive helper to mint a Schwab refresh token.

Schwab's OAuth flow requires a browser login to your actual Schwab account, which can only be
done by you, interactively, in your own browser - this script just handles the parts around
that: building the login URL, and exchanging the code Schwab hands back for a refresh token.

Run this yourself locally (not through an agent/automation) after your developer.schwab.com
app is registered and approved:

    python scripts/schwab_authorize.py

Prerequisites (set in .env or the shell):
    SCHWAB_CLIENT_ID       - your app's "App Key" from the developer portal
    SCHWAB_CLIENT_SECRET   - your app's "Secret"
    SCHWAB_REDIRECT_URI    - must exactly match the Callback URL on your app (default below)

The refresh token this prints is long-lived (7 days, and Schwab does not currently support
refreshing it without repeating this browser flow) - copy it into .env as SCHWAB_REFRESH_TOKEN.
"""
import base64
import os
import sys
import webbrowser
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

AUTHORIZE_URL = "https://api.schwabapi.com/v1/oauth/authorize"
TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
DEFAULT_REDIRECT_URI = "https://127.0.0.1:8182"


def main():
    client_id = os.getenv("SCHWAB_CLIENT_ID")
    client_secret = os.getenv("SCHWAB_CLIENT_SECRET")
    redirect_uri = os.getenv("SCHWAB_REDIRECT_URI", DEFAULT_REDIRECT_URI)

    if not client_id or not client_secret:
        sys.exit(
            "Set SCHWAB_CLIENT_ID and SCHWAB_CLIENT_SECRET first (in .env or your shell) - "
            "these come from your app on https://developer.schwab.com/dashboard/apps."
        )

    auth_url = f"{AUTHORIZE_URL}?{urlencode({'client_id': client_id, 'redirect_uri': redirect_uri})}"
    print("1. Opening your browser to log into Schwab and authorize this app.")
    print(f"   If it doesn't open automatically, visit:\n   {auth_url}\n")
    webbrowser.open(auth_url)

    print("2. After you log in and approve, Schwab redirects your browser to a URL starting")
    print(f"   with {redirect_uri} that will likely show as unreachable/refused in your")
    print("   browser - that's expected, nothing is actually listening there. Copy the FULL")
    print("   URL from the browser's address bar and paste it below.\n")
    redirected_url = input("Paste the full redirect URL here: ").strip()

    query = parse_qs(urlparse(redirected_url).query)
    if "code" not in query:
        sys.exit(f"No 'code' parameter found in that URL. Got query params: {list(query)}")
    auth_code = query["code"][0]

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    response = requests.post(
        TOKEN_URL,
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "authorization_code", "code": auth_code, "redirect_uri": redirect_uri},
        timeout=10,
    )
    response.raise_for_status()
    tokens = response.json()

    print("\nSuccess. Add this to option_data_service/.env:\n")
    print(f"SCHWAB_REFRESH_TOKEN={tokens['refresh_token']}")
    print(f"\n(Access token, valid ~30 minutes, also issued: {tokens['access_token'][:12]}... - the")
    print("SchwabProvider fetches its own short-lived access token from the refresh token on")
    print("every call, so you don't need to save this one.)")


if __name__ == "__main__":
    main()
