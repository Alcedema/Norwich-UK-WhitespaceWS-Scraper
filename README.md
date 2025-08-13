# Norwich bin collection → iCalendar (.ics)

Playwright-based scraper for Norwich City Council bin collections. Exports an **.ics** file for Domestic, Recycling, and optional Garden Waste. Runs via **Docker** or locally. Good for **Home Assistant** calendar integration.

## The need..

Norwich City Council moved to WhitespaceWS to fulfil their waste services and took down the old mynorwich links.

# Setup

Clone the repository somewhere persistent, for example under `/opt`:

```
sudo git clone https://github.com/Alcedema/Norwich-UK-WhitespaceWS-Scraper /opt/Norwich-UK-WhitespaceWS-Scraper
cd /opt/Norwich-UK-WhitespaceWS-Scraper
```

Copy `.env.example` to `.env` and edit the environment variables.

## Docker

```
docker compose build
docker compose run --rm scraper
# bins.ics -> ${LOCAL_OUTPUT_DIR:-/var/www/html}/bins.ics
```

`LOCAL_OUTPUT_DIR` controls the host directory for the generated file.

## Local Python

Create a virtual environment and install dependencies:

```
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Playwright can also install browser dependencies on most distributions with:

```
playwright install --with-deps chromium
```

Run the scraper:

```
python scrape.py
# bins.ics -> ${LOCAL_OUTPUT_DIR:-/var/www/html}/bins.ics
```

The script automatically loads the `.env` file. Schedule it with your own
cron job or systemd timer, or set `CRON_PATTERN` for built-in scheduling.

## systemd

Example unit files are provided in [`systemd/`](systemd). They assume the repository
resides in `/opt/Norwich-UK-WhitespaceWS-Scraper` with dependencies installed in a
Python virtual environment at `.venv`:

- `whitespacews-cron.service` runs the scraper continuously using the built-in cron pattern.
- `whitespacews.service` and `whitespacews.timer` run the scraper on a schedule you control with `OnCalendar`.

Copy the desired files to `/etc/systemd/system/`, tweak schedules or `ExecStart`
if your environment differs, then enable with `systemctl enable --now <unit>`.

## Environment variables

### Required

- `HOUSE_NUMBER` – property number
- `STREET_NAME` – street name
- `POSTCODE` – property postcode

### Optional

- `OUTPUT_PATH` – override calendar output path (default `${LOCAL_OUTPUT_DIR}/bins.ics`; inside the container the default is `/output/bins.ics`)
- `CRON_PATTERN` – run on an internal schedule when set, e.g. `0 8 * * *` for every day at 8:00am UTC / 9:00am BST
- `CRON_JITTER_MAX_SECONDS` – random delay before each run (default `60`, set `0` to disable – not recommended)
- `KEEP_DAYS` – past event retention: `-1` keeps all (default), `0` keeps none, `N` keeps last `N` days
- `LOCAL_OUTPUT_DIR` – host directory for the generated file used by docker compose and local runs (default `/var/www/html`)
- `DEBUG` – enable verbose logging of the scraping steps

## Scheduling

By default the scraper runs once so it can be triggered by an external cron.
Before each scrape a small random delay (jitter) of up to 60 seconds is applied
to avoid hitting the service at a perfectly predictable time. Override this with
`CRON_JITTER_MAX_SECONDS` (set to `0` to disable), but this is **not recommended**.
Set `CRON_PATTERN` in the environment (e.g. `CRON_PATTERN="0 8 * * *"`) to have
the container run the scraper on its own internal schedule, where the same
jitter is applied before every run. An initial scrape is always performed on
startup so that debug output and calendar files are produced immediately.
Whatever scheduling approach you use, ensure you abide by WhitespaceWS terms
and conditions regarding scraping intervals.

## Event retention

By default (`KEEP_DAYS=-1`) all historical events remain in the generated
calendar. Set `KEEP_DAYS` in the environment to remove events older than that
many days prior to today. For example, `KEEP_DAYS=0` keeps no past events, while
`KEEP_DAYS=7` retains only the last week's events.
