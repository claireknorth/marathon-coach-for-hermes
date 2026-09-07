#!/bin/bash
# refresh_tokens_cron.sh — silent-when-healthy wrapper for the token refresher.
#
# Runs the Python refresher, sources .env first so client creds are present,
# and produces OUTPUT ONLY when the user needs to act. Designed for a Hermes
# cron job with no_agent=True: empty stdout == silent (nothing delivered),
# non-empty stdout == a message the user sees.
#
#   exit 0  -> all fresh / refreshed OK   -> STAY SILENT (no stdout)
#   exit 1  -> transient failure           -> warn (network/API hiccup)
#   exit 2  -> refresh token dead           -> alert: needs one-time re-auth
#
set -o pipefail

ENV_FILE="/opt/data/.env"
SCRIPT="/opt/data/skills/marathon-morning-check-in/scripts/refresh_tokens.py"
LOG="/opt/data/skills/marathon-morning-check-in/scripts/refresh_tokens.log"

# Load client_id/secret etc. into env for the Strava path.
set -a
# shellcheck disable=SC1090
[ -f "$ENV_FILE" ] && . "$ENV_FILE" 2>/dev/null
set +a

OUT="$(python3 "$SCRIPT" 2>&1)"
CODE=$?

# Always keep a rolling local log (last ~200 lines) for debugging.
{
  echo "----- $(date -u '+%Y-%m-%dT%H:%M:%SZ') exit=$CODE -----"
  echo "$OUT"
} >> "$LOG" 2>/dev/null
tail -n 200 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG" 2>/dev/null

case "$CODE" in
  0)
    # Healthy — say nothing. (Silent cron => no delivery.)
    exit 0
    ;;
  2)
    echo "⚠️ Marathon coach: a token needs a ONE-TIME re-auth (it can't self-refresh)."
    echo ""
    echo "$OUT" | grep -Ei "EXPIRED|REVOKED|invalid|re-auth|rejected" | head -4
    echo ""
    echo "Google fix: re-create the OAuth client in Google Cloud Console, then run"
    echo "  python3 /opt/data/skills/marathon-morning-check-in/scripts/oob_auth.py url"
    echo "and PUBLISH the app (Testing mode tokens die every 7 days)."
    exit 2
    ;;
  *)
    echo "⚠️ Marathon coach token refresh hit a transient error (will retry next run):"
    echo "$OUT" | tail -4
    exit 1
    ;;
esac
