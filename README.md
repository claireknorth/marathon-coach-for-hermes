# Marathon Coach for Hermes Agent

A reusable marathon coaching system for Hermes Agent.

Hermes is the agent runtime. This repository is the portable coaching package:
one skill, persistent memory templates, focused reference docs, helper scripts,
and optional cron recipes.

## What It Includes

| Layer | Path | Purpose |
|---|---|---|
| Skill | `SKILL.md` | Core coaching workflow and agent instructions |
| Athlete profile | `config/athlete-profile.example.yaml` | Race, zones, location, calendar, and preferences |
| Memory scaffold | `assets/coach-memory-scaffold.md` | Persistent run log, preferences, watch items, and pace-at-HR table |
| References | `references/*.md` | Training, weather, injury, calendar, and Strava fallback guidance |
| Scripts | `scripts/*.py` | Token refresh, card rendering, and fitness-trend analysis |
| Cron recipes | `cron/*.json` | Example scheduled Hermes jobs |

## Install

```bash
cp -r . ~/.hermes/skills/marathon-morning-check-in
mkdir -p ~/.hermes/marathon
cp assets/coach-memory-scaffold.md ~/.hermes/marathon/coach-memory.md
cp config/athlete-profile.example.yaml ~/.hermes/marathon/athlete-profile.yaml
cp .env.example /opt/data/.env
```

Then edit:

- `~/.hermes/marathon/athlete-profile.yaml`
- `~/.hermes/marathon/coach-memory.md`
- `/opt/data/.env`
- `/opt/data/google_client_secret.json`

## Configure Data Sources

The package can use MCP tools when Hermes exposes them, or REST fallbacks from
the helper docs.

- Strava: set `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`,
  `STRAVA_ACCESS_TOKEN`, `STRAVA_REFRESH_TOKEN`, and `STRAVA_EXPIRES_AT`.
- Google Calendar: create an OAuth client, save the client secret JSON, then run
  `python3 scripts/oob_auth.py url` and `python3 scripts/oob_auth.py code ...`.
- Weather: Open-Meteo needs no API key.

## Run Manually

In Hermes chat:

```text
/marathon-morning-check-in run my check-in
```

Or ask naturally:

```text
what is my run today?
```

## Cron

The common pattern is a nightly prep:

```bash
hermes cron create "0 1 * * *" \
  "Run the marathon-morning-check-in skill. Review recent training, read memory and profile, check tomorrow's session and weather, then deliver a compact prep card and coaching note." \
  --skill marathon-morning-check-in \
  --name marathon-nightly-prep \
  --deliver origin
```

`0 1 * * *` is 1:00 UTC. Adjust for your runner's timezone.

## Privacy

Do not commit live `.env`, OAuth token files, Strava exports, Google client
secrets, or a real athlete's private memory unless the repo is intentionally
private and the athlete consented.

This package is designed to publish reusable logic and templates, not raw
personal health history.
