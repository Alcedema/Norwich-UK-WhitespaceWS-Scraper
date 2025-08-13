import os
import re
import hashlib
from datetime import datetime, timedelta, UTC
from pathlib import Path
from playwright.sync_api import Playwright, sync_playwright

# --- Config ---
TARGET_URL = os.getenv("TARGET_URL", "https://bnr-wrp.whitespacews.com/#!")
OUTPUT_PATH = Path(os.getenv("OUTPUT_PATH", "/output/bins.ics"))
HEADLESS = os.getenv("HEADLESS", "1") == "1"

def env_required(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v

HOUSE_NUMBER = env_required("HOUSE_NUMBER")
STREET_NAME = env_required("STREET_NAME")
POSTCODE = env_required("POSTCODE")

# --- Helpers: iCal read/write ---
def parse_ics_events(path: Path):
    events = set()
    if not path.exists():
        return events
    summary = None
    dtstart = None
    in_event = False
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if line == "BEGIN:VEVENT":
            in_event = True
            summary = None
            dtstart = None
        elif line == "END:VEVENT":
            if in_event and summary and dtstart:
                events.add((summary, dtstart))
            in_event = False
        elif in_event:
            if line.startswith("SUMMARY:"):
                summary = line[len("SUMMARY:"):].strip()
            elif line.startswith("DTSTART;VALUE=DATE:"):
                dtstart = line.split(":", 1)[1].strip()
            elif line.startswith("DTSTART:") and ";" not in line:
                dtstart = line.split(":", 1)[1].strip()
    return events

def ics_header():
    return (
        "BEGIN:VCALENDAR\r\n"
        "PRODID:-//Tim Bin Export//Playwright//EN\r\n"
        "VERSION:2.0\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:PUBLISH\r\n"
    )

def ics_footer():
    return "END:VCALENDAR\r\n"

def fold(line: str) -> str:
    out, width, buf = [], 0, []
    for ch in line:
        buf.append(ch)
        width += 1
        if width >= 73:
            out.append("".join(buf))
            buf = ["\r\n "]
            width = 1
    out.append("".join(buf))
    return "".join(out)

def event_block(summary: str, yyyymmdd: str) -> str:
    dt = datetime.strptime(yyyymmdd, "%Y%m%d")
    dtend = (dt + timedelta(days=1)).strftime("%Y%m%d")
    uid_src = f"{summary}|{yyyymmdd}|bins-norwich"
    uid = hashlib.sha1(uid_src.encode()).hexdigest() + "@bins"
    now = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now}",
        f"DTSTART;VALUE=DATE:{yyyymmdd}",
        f"DTEND;VALUE=DATE:{dtend}",
        fold(f"SUMMARY:{summary}"),
        "END:VEVENT",
    ]
    return "\r\n".join(lines) + "\r\n"

def append_events(path: Path, new_events: list[tuple[str, str]]):
    existing = parse_ics_events(path)
    to_add = [(s, d) for (s, d) in new_events if (s, d) not in existing]
    if not to_add and path.exists():
        return
    pieces = []
    if path.exists():
        content = path.read_text(encoding="utf-8", errors="ignore")
        if not content.strip().endswith("END:VCALENDAR"):
            content = (content.rstrip() + "\r\n" + ics_footer())
        content = content.rstrip("\r\n")
        content = content[: content.rfind("END:VCALENDAR")]
        pieces.append(content)
    else:
        pieces.append(ics_header())
    for s, d in to_add:
        pieces.append(event_block(s, d))
    pieces.append(ics_footer())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(pieces), encoding="utf-8")

# --- Scrape parsing ---
SERVICE_RE = re.compile(
    r"(?P<date>\b\d{2}/\d{2}/\d{4}\b).*?(?P<service>\b(?:Domestic|Food|Garden|Recycling)\b).*?Collection Service",
    re.IGNORECASE | re.DOTALL,
)

def extract_events_from_html(html: str):
    events = []
    for m in SERVICE_RE.finditer(html):
        dmy = m.group("date")
        typ = m.group("service")
        summary = typ.split()[0].capitalize()
        dt = datetime.strptime(dmy, "%d/%m/%Y").strftime("%Y%m%d")
        if (summary, dt) not in events:
            events.append((summary, dt))
    return events

# --- Playwright flow ---
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

    # Select the FIRST address result (robust: links containing a comma look like address entries)
    addr_links = page.get_by_role("link").filter(has_text=re.compile(r","))
    addr_links.first.wait_for()
    addr_links.first.click()

    page.wait_for_load_state("networkidle")

    html = page.content()
    events = extract_events_from_html(html)
    append_events(OUTPUT_PATH, events)

    context.storage_state(path="auth.json")
    context.close()
    browser.close()

if __name__ == "__main__":
    with sync_playwright() as pw:
        run(pw)
