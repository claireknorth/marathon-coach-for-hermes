# Token Auto-Refresh

The package includes a stdlib-only token refresher:

```bash
python3 scripts/refresh_tokens.py
```

It refreshes:

- Strava access and refresh tokens stored in `/opt/data/.env`
- Google Calendar access tokens stored in `/opt/data/google_token.json`

Strava rotates refresh tokens on every refresh, so the script writes the new
refresh token back to `.env`.

Google does not usually rotate refresh tokens. If Google returns `invalid_grant`,
the athlete needs to complete OAuth setup again. If a Google OAuth app is left in
Testing mode, refresh tokens may expire after about a week; publish the app for
long-running unattended use.

The cron wrapper `scripts/refresh_tokens_cron.sh` stays silent when healthy and
prints only when user action is required.
