# Open-Meteo Weather

Open-Meteo provides free forecast and historical weather data without an API key.

## Forecast URL

```text
https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&hourly=temperature_2m,apparent_temperature,dew_point_2m,precipitation_probability,wind_speed_10m&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone={TIMEZONE}
```

Use the athlete's home latitude, longitude, and timezone from
`athlete-profile.yaml`, unless recent activity GPS indicates travel.

## Dew Point Labels

| Dew point | Label | Coaching meaning |
|---:|---|---|
| under 55F | dry | Normal pacing |
| 55-60F | comfortable | Slightly noticeable |
| 60-65F | sticky | Use HR over pace |
| 65-70F | hard | Slow down, hydrate |
| 70F+ | oppressive | Consider moving indoors or shortening |
