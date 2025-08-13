# scrape.py (async, no greenlet needed)
import os, re, hashlib
from pathlib import Path
from datetime import datetime, timedelta, date, UTC
from ics import Calendar, Event
from playwright.async_api import async_playwright

TARGET_URL  = os.getenv("TARGET_URL", "https://bnr-wrp.whitespacews.com/#!")
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "/output/bins.ics"))
HEADLESS    = os.getenv("HEADLESS", "1") == "1"

def env_required(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v

HOUSE_NUMBER = env_required("HOUSE_NUMBER")
STREET_NAME  = env_required("STREET_NAME")
POSTCODE     = env_required("POSTCODE")

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
        ev = Event(name=summary)
        ev.begin = d
        ev.end = d + timedelta(days=1)
        ev.uid = make_uid(summary, d)
        ev.created = ev.last_modified = datetime.now(UTC)
        cal.events.add(ev); added += 1
    return added

def save_calendar(path: Path, cal: Calendar):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(cal), encoding="utf-8")

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context(locale="en-GB", timezone_id="Europe/London")
        page = await context.new_page()

        await page.goto(TARGET_URL, wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle")

        await page.get_by_role("link", name="View my collections").click()
        await page.get_by_role("textbox", name="Property name or number").fill(HOUSE_NUMBER)
        await page.get_by_role("textbox", name="Street name").fill(STREET_NAME)
        await page.get_by_role("textbox", name="Postcode").fill(POSTCODE)
        await page.get_by_role("button", name="Continue").click()

        addr_links = page.get_by_role("link").filter(has_text=re.compile(r","))
        await addr_links.first.wait_for()
        await addr_links.first.click()
        await page.wait_for_load_state("networkidle")

        html = await page.content()
        items = extract_events_from_html(html)

        cal = load_calendar(OUTPUT_PATH)
        if add_events(cal, items) or not OUTPUT_PATH.exists():
            save_calendar(OUTPUT_PATH, cal)

        await context.close(); await browser.close()

if __name__ == "__main__":
    import asyncio; asyncio.run(run())
