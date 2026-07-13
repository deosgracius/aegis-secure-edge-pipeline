"""
oauth.py -- Google OAuth 2.0 / OIDC login (authorization-code flow).

Flow:
  1. /auth/oauth/login  -> redirect the user to build_authorization_url(...)
  2. Google redirects back to /auth/oauth/callback?code=...
  3. exchange_code(code) swaps the code for tokens and reads the verified email
     from Google's userinfo endpoint (so we don't hand-verify a JWT).
  4. store.oauth_login(email) maps an allow-listed email to a role + session.

The HTTP round-trip to Google needs the real consent screen, so it can't be
exercised headlessly; the email->session mapping (the security-relevant part)
is unit-tested in verify_oauth.py.
"""

import urllib.parse

import httpx

import config

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"


def build_authorization_url(state):
    c = config.google_oauth()
    params = {
        "client_id": c["client_id"],
        "redirect_uri": c["redirect_uri"],
        "response_type": "code",
        "scope": "openid email",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return AUTH_ENDPOINT + "?" + urllib.parse.urlencode(params)


def exchange_code(code):
    """Swap an auth code for a verified email. Returns the email or None."""
    c = config.google_oauth()
    with httpx.Client(timeout=10) as client:
        tok = client.post(TOKEN_ENDPOINT, data={
            "code": code,
            "client_id": c["client_id"],
            "client_secret": c["client_secret"],
            "redirect_uri": c["redirect_uri"],
            "grant_type": "authorization_code",
        })
        if tok.status_code != 200:
            return None
        access_token = tok.json().get("access_token")
        if not access_token:
            return None
        info = client.get(USERINFO_ENDPOINT,
                          headers={"Authorization": "Bearer " + access_token})
        if info.status_code != 200:
            return None
        data = info.json()
        if not data.get("email_verified"):
            return None
        return data.get("email")
