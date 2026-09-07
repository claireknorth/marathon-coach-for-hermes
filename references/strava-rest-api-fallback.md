# Strava REST API Fallback

Use this when Hermes does not expose Strava MCP tools.

## Environment

```bash
set -a
. /opt/data/.env
set +a
```

## Recent Activities

```bash
curl -s "https://www.strava.com/api/v3/athlete/activities?per_page=10" \
  -H "Authorization: Bearer $STRAVA_ACCESS_TOKEN"
```

Useful fields:

- `type`
- `name`
- `distance`
- `moving_time`
- `average_heartrate`
- `max_heartrate`
- `total_elevation_gain`
- `start_date_local`
- `average_speed`
- `suffer_score`

Convert meters to miles with `distance / 1609.34`. Convert m/s to min/mi with
`1609.34 / average_speed / 60`.

If a call returns `401`, run:

```bash
python3 scripts/refresh_tokens.py strava --force
```
