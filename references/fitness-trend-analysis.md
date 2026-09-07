# Fitness Trend Analysis

The cleanest endurance signal is pace at a comparable heart rate, with heat and
humidity accounted for.

Use:

```bash
python3 scripts/fitness_trend.py --since YYYY-MM-DD
```

The script:

- pulls Strava runs with heart-rate data
- filters for aerobic/easy road runs
- fetches historical dew point from Open-Meteo
- normalizes pace to a cool-weather baseline
- compares early vs recent windows

Treat the result as one signal, not a diagnosis. Fatigue, terrain, illness,
sleep, heat, and sensor errors can all distort the trend.
