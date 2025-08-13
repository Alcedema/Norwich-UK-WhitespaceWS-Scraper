# The need..

Norwich City Council moved to WhitespaceWS to fulfil their waste services and took down the old map logic

# To use..

Edit the environment variables in `compose.yaml` (see below), then:

```
docker compose build
docker compose run --rm scraper
# bins.ics -> /output/bins.ics
```

`LOCAL_OUTPUT_DIR` controls the host directory for the generated file and
defaults to `/var/www/html`.

## Environment variables

### Required

- `HOUSE_NUMBER` – property number
- `STREET_NAME` – street name
- `POSTCODE` – property postcode

### Optional

- `OUTPUT_PATH` – override calendar output path (default `/output/bins.ics`)
- `CRON_PATTERN` – run on an internal schedule when set, e.g. `0 8 * * *` for every day at 8:00am UTC / 9:00am BST
- `CRON_JITTER_MAX_SECONDS` – random delay before each run (default `60`, set `0` to disable)
- `KEEP_DAYS` – remove events older than this many days

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
