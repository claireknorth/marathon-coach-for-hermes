#!/usr/bin/env python3
"""
refresh_tokens.py — Self-healing OAuth token refresher for the marathon coach.

Refreshes Strava and Google (Runna calendar) access tokens using their
long-lived refresh tokens, then persists the new access tokens back to disk
so every downstream consumer (MCP server, curl calls, the google-auth path)
sees a fresh token. Pure Python stdlib only (urllib) — no pip deps required,
so it runs identically in cron/unattended mode.

USAGE
    python3 refresh_tokens.py            # refresh both, only if near expiry
    python3 refresh_tokens.py --force    # refresh both regardless of expiry
    python3 refresh_tokens.py strava     # refresh only Strava
    python3 refresh_tokens.py google     # refresh only Google
    python3 refresh_tokens.py --status   # show expiry status, refresh nothing

EXIT CODES
    0  all requested refreshes succeeded (or were skipped as still-fresh)
    1  a refresh failed with a retryable/transient error
    2  a refresh token is expired/revoked -> needs full manual re-auth
       (Google Testing-mode tokens die every 7 days; publish the app to fix)

DESIGN NOTES
  - Strava tokens live in /opt/data/.env as STRAVA_ACCESS_TOKEN etc. Strava
    ROTATES the refresh token on every refresh, so we persist BOTH the new
    access token and the new refresh token back to .env.
  - Google token lives in /opt/data/google_token.json in the RAW oauth
    response shape (access_token, refresh_token, expires_in, scope, ...).
    We refresh via the token endpoint and rewrite the file preserving
    refresh_token + scope. Google does NOT rotate the refresh token.
  - We never print secret values. Logs show only status + expiry math.
  - "invalid_grant" from Google == refresh token dead -> exit 2 so the caller
    knows this needs human re-auth, not a retry.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ENV_PATH = os.environ.get("HERMES_ENV_PATH", "/opt/data/.env")
GOOGLE_TOKEN_PATH = os.environ.get("GOOGLE_TOKEN_PATH", "/opt/data/google_token.json")
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
STRAVA_TOKEN_URI = "https://www.strava.com/oauth/token"

# Refresh if the access token expires within this many seconds.
STRAVA_SKEW = 20 * 60   # 20 min buffer (Strava tokens last ~6h)
GOOGLE_SKEW = 10 * 60   # 10 min buffer (Google access tokens last ~1h)


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    print(f"[{ts}] {msg}", flush=True)


def _post_form(url, fields):
    """POST application/x-www-form-urlencoded, return (status, parsed_json)."""
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body}


# ---------------------------------------------------------------------------
# .env helpers
# ---------------------------------------------------------------------------
def read_env():
    env = {}
    if not os.path.exists(ENV_PATH):
        return env
    with open(ENV_PATH) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v
    return env


def set_env_var(key, value):
    """Set or replace KEY=value in .env, preserving all other lines. Atomic write."""
    lines = []
    found = False
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            lines = f.readlines()
    pat = re.compile(rf"^{re.escape(key)}=")
    for i, line in enumerate(lines):
        if pat.match(line):
            lines[i] = f"{key}={value}\n"
            found = True
            break
    if not found:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(f"{key}={value}\n")
    tmp = ENV_PATH + ".tmp"
    with open(tmp, "w") as f:
        f.writelines(lines)
    os.replace(tmp, ENV_PATH)


# ---------------------------------------------------------------------------
# Strava
# ---------------------------------------------------------------------------
def strava_status(env):
    """Return seconds-until-expiry, or None if unknown."""
    exp = env.get("STRAVA_EXPIRES_AT")
    if exp and exp.isdigit():
        return int(exp) - int(time.time())
    return None


def refresh_strava(force=False):
    env = read_env()
    cid = env.get("STRAVA_CLIENT_ID")
    csec = env.get("STRAVA_CLIENT_SECRET")
    rtok = env.get("STRAVA_REFRESH_TOKEN")
    if not (cid and csec and rtok):
        log("STRAVA: missing CLIENT_ID/CLIENT_SECRET/REFRESH_TOKEN in .env — skipping")
        return 1

    ttl = strava_status(env)
    if ttl is not None and ttl > STRAVA_SKEW and not force:
        log(f"STRAVA: token still fresh ({ttl // 60} min left) — skip")
        return 0

    log("STRAVA: refreshing access token...")
    status, body = _post_form(STRAVA_TOKEN_URI, {
        "client_id": cid,
        "client_secret": csec,
        "grant_type": "refresh_token",
        "refresh_token": rtok,
    })
    if status == 200 and "access_token" in body:
        set_env_var("STRAVA_ACCESS_TOKEN", body["access_token"])
        # Strava rotates the refresh token — persist the new one or the next
        # refresh will fail.
        if body.get("refresh_token"):
            set_env_var("STRAVA_REFRESH_TOKEN", body["refresh_token"])
        if body.get("expires_at"):
            set_env_var("STRAVA_EXPIRES_AT", str(body["expires_at"]))
        mins = (int(body.get("expires_at", 0)) - int(time.time())) // 60
        log(f"STRAVA: refreshed OK (expires in ~{mins} min)")
        return 0
    if status in (400, 401) and "invalid" in json.dumps(body).lower():
        log(f"STRAVA: refresh token rejected ({status}) — needs re-auth via Strava OAuth")
        return 2
    log(f"STRAVA: refresh failed status={status} body={body}")
    return 1


# ---------------------------------------------------------------------------
# Google
# ---------------------------------------------------------------------------
def google_status(tok):
    """Return seconds-until-expiry using our stored 'obtained_at' + expires_in."""
    obtained = tok.get("obtained_at")
    expires_in = tok.get("expires_in")
    if obtained and expires_in:
        return int(obtained) + int(expires_in) - int(time.time())
    return None


def refresh_google(force=False):
    if not os.path.exists(GOOGLE_TOKEN_PATH):
        log(f"GOOGLE: no token file at {GOOGLE_TOKEN_PATH} — skipping")
        return 1
    with open(GOOGLE_TOKEN_PATH) as f:
        tok = json.load(f)

    cid = tok.get("client_id")
    csec = tok.get("client_secret")
    rtok = tok.get("refresh_token")
    if not (cid and csec and rtok):
        log("GOOGLE: token file missing client_id/client_secret/refresh_token — needs re-auth")
        return 2

    ttl = google_status(tok)
    if ttl is not None and ttl > GOOGLE_SKEW and not force:
        log(f"GOOGLE: token still fresh ({ttl // 60} min left) — skip")
        return 0

    log("GOOGLE: refreshing access token...")
    status, body = _post_form(GOOGLE_TOKEN_URI, {
        "client_id": cid,
        "client_secret": csec,
        "grant_type": "refresh_token",
        "refresh_token": rtok,
    })
    if status == 200 and "access_token" in body:
        tok["access_token"] = body["access_token"]
        tok["expires_in"] = body.get("expires_in", 3600)
        tok["obtained_at"] = int(time.time())
        if body.get("scope"):
            tok["scope"] = body["scope"]
        # Google does NOT rotate refresh tokens; keep the existing one.
        tmp = GOOGLE_TOKEN_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(tok, f, indent=2)
        os.replace(tmp, GOOGLE_TOKEN_PATH)
        log(f"GOOGLE: refreshed OK (expires in ~{tok['expires_in'] // 60} min)")
        return 0

    err = (body.get("error") or "").lower()
    if err == "invalid_grant":
        log("GOOGLE: refresh token EXPIRED/REVOKED (invalid_grant). "
            "This is the Testing-mode 7-day expiry. Re-auth with oob_auth.py, "
            "or publish the OAuth app in Google Cloud Console for a permanent fix.")
        return 2
    if err == "invalid_client":
        log("GOOGLE: OAuth CLIENT rejected (invalid_client) — the client was "
            "deleted or its secret rotated in Google Cloud Console. This is NOT "
            "a token problem; no refresh can fix it. Create a fresh OAuth client, "
            "download the client secret, then re-auth with oob_auth.py.")
        return 2
    log(f"GOOGLE: refresh failed status={status} body={body}")
    return 1


# ---------------------------------------------------------------------------
# status view
# ---------------------------------------------------------------------------
def show_status():
    env = read_env()
    st = strava_status(env)
    if st is None:
        log("STRAVA: expiry unknown (no STRAVA_EXPIRES_AT recorded yet)")
    else:
        log(f"STRAVA: access token expires in {st // 60} min "
            f"({'STALE' if st < STRAVA_SKEW else 'ok'})")

    if os.path.exists(GOOGLE_TOKEN_PATH):
        with open(GOOGLE_TOKEN_PATH) as f:
            tok = json.load(f)
        gt = google_status(tok)
        if gt is None:
            log("GOOGLE: expiry unknown (no obtained_at recorded yet — run a refresh once)")
        else:
            log(f"GOOGLE: access token expires in {gt // 60} min "
                f"({'STALE' if gt < GOOGLE_SKEW else 'ok'})")
    else:
        log("GOOGLE: no token file")


def main(argv):
    force = "--force" in argv
    args = [a for a in argv if not a.startswith("--")]

    if "--status" in argv:
        show_status()
        return 0

    targets = args if args else ["strava", "google"]
    codes = []
    if "strava" in targets:
        codes.append(refresh_strava(force=force))
    if "google" in targets:
        codes.append(refresh_google(force=force))

    # Worst-case exit code wins: 2 (needs re-auth) > 1 (transient) > 0 (ok)
    if 2 in codes:
        return 2
    if 1 in codes:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
