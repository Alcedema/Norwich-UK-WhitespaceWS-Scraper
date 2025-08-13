# The need..

Norwich City Council moved to WhitespaceWS to fulfil their waste services and took down the old map logic

# To use..

```
cp .env.example .env   # edit values
docker compose build
docker compose run --rm scraper
# bins.ics -> /output/bins.ics
```

## Scheduling

By default the scraper runs once so it can be triggered by an external cron.
Set `CRON_PATTERN` in the environment (e.g. `CRON_PATTERN="0 8 * * *"`) to
have the container run the scraper on its own internal schedule.
