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
Before each scrape a small random delay (jitter) of up to 60 seconds is applied
to avoid hitting the service at a perfectly predictable time. Override this with
`CRON_JITTER_MAX_SECONDS` (set to `0` to disable), but this is **not recommended**.
Set `CRON_PATTERN` in the environment (e.g. `CRON_PATTERN="0 8 * * *"`) to have
the container run the scraper on its own internal schedule, where the same
jitter is applied before every run. Whatever scheduling approach you use,
ensure you abide by WhitespaceWS terms and conditions regarding scraping
intervals.

## Event retention

By default all historical events remain in the generated calendar. Set
`KEEP_DAYS` in the environment to remove events older than that many days prior
to today. For example, `KEEP_DAYS=0` keeps no past events, while
`KEEP_DAYS=7` retains only the last week's events.
