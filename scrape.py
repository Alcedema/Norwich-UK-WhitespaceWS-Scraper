# scrape.py
import os
import re
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, UTC, date
from playwright.sync_api import Playwright, sync_playwright
from ics import Calendar, Event

# ---- Config ----
TARGET_URL = os.getenv("TARGET_URL", "https://bnr-wrp.whitespacews.com/#!")
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "/output/bins.ics"))
HEADLESS = os.getenv("HEADLESS", "1") == "1"

def env_required(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v

HOUSE_NUMBER = env_required("HOUSE_NUMBER")
STREET_NAME  = env_required("STREET_NAME")
POSTCODE     = env_required("POSTCODE")

# ---- Scrape parsing ----
SERVICE_RE = re.compile(
    r"(?P<date>\b\d{2}/\d{2}/\d{4}\b).*?(?P<service>\b(?:Domestic|Food|Garden|Recycling)\b).*?Collection Service",
    re.IGNORECASE | re.DOTALL,
)

def extract_events_from_html(html: str):
    """Return list of (summary:str, event_date:date)."""
    out, seen = [], set()
    for m in SERVICE_RE.finditer(html):
        dmy = m.group("date")
        typ = m.group("service")
        summary = typ.split()[0].capitalize()
        d = datetime.strptime(dmy, "%d/%m/%Y").date()
        key = (summary, d)
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out

# ---- ICS helpers (using `ics`) ----
def load_calendar(path: Path) -> Calendar:
    if path.exists():
        return Calendar(path.read_text(encoding="utf-8", errors="ignore"))
    return Calendar()

def make_uid(summary: str, d: date) -> str:
    base = f"{summary}|{d.isoformat()}|bins-norwich"
    return hashlib.sha1(base.encode()).hexdigest() + "@bins"

def calendar_keys(cal: Calendar):
    """Set of (summary, date) from existing events (all-day assumed)."""
    keys = set()
    for ev in cal.events:
        # If all-day, ev.begin.date() is correct; end is exclusive
        try:
            s = (ev.name or "").strip()
            d = ev.begin.date()
            keys.add((s, d))
        except Exception:
            continue
    return keys

def add_events(cal: Calendar, new_items: list[tuple[str, date]]) -> int:
    existing = calendar_keys(cal)
    added = 0
    for summary, d in new_items:
        if (summary, d) in existing:
            continue
        ev = Event()
        ev.name = summary
        ev.begin = d  # date ⇒ all-day when saved (we also ensure end)
        ev.end = d + timedelta(days=1)  # exclusive end for all-day
        ev.uid = make_uid(summary, d)
        # RFC-compliant stamp (UTC)
        ev.created = datetime.now(UTC)
        ev.last_modified = ev.created
        cal.events.add(ev)
        added += 1
    return added

def save_calendar(path: Path, cal: Calendar):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(cal), encoding="utf-8")

# ---- Playwright flow ----
def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=HEADLESS)
    context = browser.new_context(locale="en-GB", timezone_id="Europe/London")
    page = context.new_page()

    page.goto(TARGET_URL, wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")

    page.get_by_role("link", name="View my collections").click()
    page.get_by_role("textbox", name="Property name or number").fill(HOUSE_NUMBER)
    page.get_by_role("textbox", name="Street name").fill(STREET_NAME)
    page.get_by_role("textbox", name="Postcode").fill(POSTCODE)
    page.get_by_role("button", name="Continue").click()

    # click the first address result (links with commas look like address rows)
    addr_links = page.get_by_role("link").filter(has_text=re.compile(r","))
    addr_links.first.wait_for()
    addr_links.first.click()

    page.wait_for_load_state("networkidle")

    html = page.content()
    items = extract_events_from_html(html)

    cal = load_calendar(OUTPUT_PATH)
    added = add_events(cal, items)
    if added or not OUTPUT_PATH.exists():
        save_calendar(OUTPUT_PATH, cal)

    context.close()
    browser.close()

if __name__ == "__main__":
    with sync_playwright() as pw:
        run(pw)
