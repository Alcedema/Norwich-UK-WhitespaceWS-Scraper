# scrape.py (async, no greenlet needed)
import os, re, hashlib, asyncio, random
from pathlib import Path
from datetime import datetime, timedelta, date, UTC
from dotenv import load_dotenv
from ics import Calendar, Event
from playwright.async_api import async_playwright

load_dotenv()
TARGET_URL         = os.getenv("TARGET_URL", "https://bnr-wrp.whitespacews.com/#!")
DEFAULT_OUTPUT_DIR = Path(os.getenv("LOCAL_OUTPUT_DIR", "/var/www/html"))
OUTPUT_PATH        = Path(os.getenv("OUTPUT_PATH") or DEFAULT_OUTPUT_DIR / "bins.ics")
HEADLESS           = os.getenv("HEADLESS", "1") == "1"
DEBUG              = os.getenv("DEBUG", "0").lower() not in ("0", "false", "")

def debug(*args):
    if DEBUG:
        print("[DEBUG]", *args)

def env_int(name: str, default: int) -> int:
    v = os.getenv(name, "").strip()
    if v == "":
        return default
    try:
        return int(v)
    except ValueError:
        raise RuntimeError(f"{name} must be an integer: {v}")

CRON_JITTER_MAX_SECONDS = env_int("CRON_JITTER_MAX_SECONDS", 60)
if CRON_JITTER_MAX_SECONDS < 0:
    raise RuntimeError("CRON_JITTER_MAX_SECONDS must be >= 0")

# -1 keeps all, 0 keeps none, N keeps last N days
KEEP_DAYS = env_int("KEEP_DAYS", -1)
if KEEP_DAYS < -1:
    raise RuntimeError("KEEP_DAYS must be -1, 0, or a positive integer")

POSTCODE_RE = re.compile(r"^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$", re.I)

def env_required(name: str, validator=None) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    if validator and not validator(v):
        raise RuntimeError(f"Invalid value for {name}: {v}")
    return v

HOUSE_NUMBER = env_required("HOUSE_NUMBER")
STREET_NAME  = env_required("STREET_NAME")
POSTCODE     = env_required("POSTCODE", lambda v: POSTCODE_RE.fullmatch(v)).upper()

SERVICE_RE = re.compile(
    r"(?P<date>\b\d{2}/\d{2}/\d{4}\b).*?(?P<service>\b(?:Domestic|Food|Garden|Recycling)\b).*?Collection Service",
    re.IGNORECASE | re.DOTALL,
)

def extract_events_from_html(html: str):
    out, seen = [], set()
    for m in SERVICE_RE.finditer(html):
        d = datetime.strptime(m.group("date"), "%d/%m/%Y").date()
        s = m.group("service").split()[0].capitalize()
        if (s, d) not in seen:
            seen.add((s, d)); out.append((s, d))
            debug(f"Found event: {s} on {d}")
    return out

def load_calendar(path: Path) -> Calendar:
    return Calendar(path.read_text(encoding="utf-8", errors="ignore")) if path.exists() else Calendar()

def make_uid(summary: str, d: date) -> str:
    return hashlib.sha1(f"{summary}|{d.isoformat()}|bins-norwich".encode()).hexdigest() + "@bins"

def calendar_keys(cal: Calendar):
    keys = set()
    for ev in cal.events:
        try:
            keys.add(((ev.name or "").strip(), ev.begin.date()))
        except Exception:
            pass
    return keys

def add_events(cal: Calendar, items: list[tuple[str, date]]) -> int:
    existing, added = calendar_keys(cal), 0
    for summary, d in items:
        if (summary, d) in existing: continue
        debug(f"Adding event: {summary} on {d}")
        ev = Event(name=summary)
        ev.begin = d
        ev.make_all_day()
        ev.uid = make_uid(summary, d)
        ev.created = ev.last_modified = datetime.now(UTC)
        cal.events.add(ev); added += 1
    return added

def prune_events(cal: Calendar, keep_days: int) -> int:
    if keep_days < 0:
        return 0
    cutoff = date.today() - timedelta(days=keep_days)
    removed = 0
    for ev in list(cal.events):
        try:
            ev_date = ev.begin.date()
        except Exception:
            continue
        if ev_date < cutoff:
            debug(f"Pruning event: {(ev.name or '').strip()} on {ev_date}")
            cal.events.remove(ev)
            removed += 1
    return removed

def save_calendar(path: Path, cal: Calendar):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cal.serialize(), encoding="utf-8")


async def run():
    async with async_playwright() as p:
        debug(f"Launching browser (headless={HEADLESS})")
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context(locale="en-GB", timezone_id="Europe/London")
        page = await context.new_page()

        debug(f"Navigating to {TARGET_URL}")
        await page.goto(TARGET_URL, wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle")
        if DEBUG:
            content = await page.content()
            debug("'View my collections' link present:", "View my collections" in content)

        debug("Clicking 'View my collections'")
        await page.get_by_role("link", name="View my collections").click()

        debug("Filling form fields")
        await page.get_by_role("textbox", name="Property name or number").fill(HOUSE_NUMBER)
        debug(f"Filled house number: {HOUSE_NUMBER}")
        await page.get_by_role("textbox", name="Street name").fill(STREET_NAME)
        debug(f"Filled street name: {STREET_NAME}")
        await page.get_by_role("textbox", name="Postcode").fill(POSTCODE)
        debug(f"Filled postcode: {POSTCODE}")

        debug("Submitting search")
        await page.get_by_role("button", name="Continue").click()

        addr_links = page.get_by_role("link").filter(has_text=re.compile(r","))
        await addr_links.first.wait_for()
        if DEBUG:
            links = await addr_links.all()
            debug(f"Found {len(links)} address link(s)")
        debug("Selecting first address")
        await addr_links.first.click()
        await page.wait_for_load_state("networkidle")

        html = await page.content()
        debug("'Waste Collection Service' in final page:", "Waste Collection Service" in html)
        items = extract_events_from_html(html)
        debug(f"Extracted {len(items)} event(s): {items}")

        cal = load_calendar(OUTPUT_PATH)
        added = add_events(cal, items)
        removed = prune_events(cal, KEEP_DAYS)
        debug(f"Calendar updates - added: {added}, removed: {removed}")
        if added or removed or not OUTPUT_PATH.exists():
            debug(f"Saving calendar to {OUTPUT_PATH}")
            save_calendar(OUTPUT_PATH, cal)

        await context.close(); await browser.close()


async def main():
    pattern = os.getenv("CRON_PATTERN", "").strip()
    if CRON_JITTER_MAX_SECONDS == 0:
        print(
            "CRON jitter disabled (not recommended).\n"
            "Please abide by WhitespaceWS terms and conditions regarding scraping intervals."
        )
    else:
        print(
            f"Applying random jitter up to {CRON_JITTER_MAX_SECONDS}s to avoid predictable scraping."
        )
        print(
            "Set CRON_JITTER_MAX_SECONDS=0 to disable (not recommended).\n"
            "Please abide by WhitespaceWS terms and conditions regarding scraping intervals."
        )
    initial_jitter = random.uniform(0, CRON_JITTER_MAX_SECONDS)
    if initial_jitter:
        print(f"Initial sleep for {initial_jitter:.0f}s")
        await asyncio.sleep(initial_jitter)

    # Always perform an initial run so DEBUG output is shown and the calendar
    # is generated even when a CRON pattern is supplied.
    await run()
    if not pattern:
        return

    from croniter import croniter
    while True:
        now = datetime.now()
        itr = croniter(pattern, now)
        next_time = itr.get_next(datetime)
        jitter = random.uniform(0, CRON_JITTER_MAX_SECONDS)
        sleep_for = (next_time - now).total_seconds() + jitter
        print(f"Sleeping for {sleep_for:.0f}s (includes {jitter:.0f}s jitter)")
        await asyncio.sleep(sleep_for)
        await run()


if __name__ == "__main__":
    asyncio.run(main())
