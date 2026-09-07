#!/usr/bin/env python3
"""
oob_auth.py — Google Calendar OAuth for headless / mobile use (2026-compatible).

The old urn:ietf:wg:oauth:2.0:oob flow was shut down by Google in 2023. This
version uses the manual loopback-copy flow that still works on a headless box:

  1. `python3 oob_auth.py url`  -> prints an auth URL.
  2. Open it in ANY browser (phone or laptop), approve access.
  3. Google redirects to http://localhost/?code=XXXX&... The page will fail to
     load (nothing is listening) — that's fine. Copy the `code` value out of the
     browser's address bar.
  4. `python3 oob_auth.py code THE_CODE`  -> exchanges it, writes the token.

Stdlib only (urllib) — no `requests`, no google-auth-oauthlib, so it runs on the
slim container. Client credentials are read from the client-secret JSON, never
hardcoded, so re-issuing a client in Google Cloud Console needs no code edits.

The saved token includes access_token, refresh_token, client_id, client_secret,
token_uri, scope(s), and obtained_at so refresh_tokens.py can auto-refresh it.
"""
import base64
import hashlib
import json
import os
import secrets
import sys
import time
import urllib.parse
import urllib.request

CLIENT_SECRET_PATH = os.environ.get(
    "GOOGLE_CLIENT_SECRET_PATH", "/opt/data/google_client_secret.json"
)
TOKEN_PATH = os.environ.get("GOOGLE_TOKEN_PATH", "/opt/data/google_token.json")
STATE_FILE = os.environ.get("GOOGLE_OAUTH_STATE", "/opt/data/.oauth_state.json")

AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
# Manual-copy loopback: Google redirects here, page fails to load, user copies
# the ?code= param from the address bar. Replaces the dead OOB redirect.
REDIRECT = "http://localhost"


def load_client():
    with open(CLIENT_SECRET_PATH) as f:
        data = json.load(f)
    # client-secret JSON wraps creds under "installed" or "web"
    inner = data.get("installed") or data.get("web") or data
    cid = inner["client_id"]
    csec = inner["client_secret"]
    return cid, csec


def _post_form(url, fields):
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"error": f"http_{e.code}"}


def get_auth_url():
    cid, _ = load_client()
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    state = secrets.token_hex(16)
    with open(STATE_FILE, "w") as f:
        json.dump({"code_verifier": code_verifier, "state": state}, f)
    os.chmod(STATE_FILE, 0o600)

    params = {
        "response_type": "code",
        "client_id": cid,
        "redirect_uri": REDIRECT,
        "scope": SCOPE,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
    }
    print(f"{AUTH_URI}?{urllib.parse.urlencode(params)}")
    print("", file=sys.stderr)
    print("Open the URL above, approve, then copy the `code` value from the", file=sys.stderr)
    print("http://localhost/?code=... address bar (the page won't load — normal).", file=sys.stderr)
    print("Then run:  python3 oob_auth.py code THE_CODE", file=sys.stderr)


def exchange_code(code):
    cid, csec = load_client()
    # URL-decode in case the user pasted the raw %2F-encoded code.
    code = urllib.parse.unquote(code)
    with open(STATE_FILE) as f:
        saved = json.load(f)

    data = _post_form(
        TOKEN_URI,
        {
            "code": code,
            "client_id": cid,
            "client_secret": csec,
            "redirect_uri": REDIRECT,
            "grant_type": "authorization_code",
            "code_verifier": saved["code_verifier"],
        },
    )
    if "error" in data or "access_token" not in data:
        print(f"ERROR: {data}", file=sys.stderr)
        sys.exit(1)

    token_data = {
        "access_token": data["access_token"],
        "expires_in": data.get("expires_in", 3599),
        "obtained_at": int(time.time()),
        "refresh_token": data["refresh_token"],
        "token_uri": TOKEN_URI,
        "client_id": cid,
        "client_secret": csec,
        "scope": SCOPE,
        "scopes": [SCOPE],
        "token_type": "Bearer",
    }
    tmp = TOKEN_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(token_data, f, indent=2)
    os.replace(tmp, TOKEN_PATH)
    os.chmod(TOKEN_PATH, 0o600)
    print(f"OK: token saved to {TOKEN_PATH}")
    print("Verify with: python3 refresh_tokens.py google --force")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "url":
        get_auth_url()
    elif cmd == "code" and len(sys.argv) > 2:
        exchange_code(sys.argv[2])
    else:
        print("Usage: oob_auth.py url | oob_auth.py code THE_CODE", file=sys.stderr)
        sys.exit(1)
