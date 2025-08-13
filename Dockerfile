FROM python:3.13-slim AS builder
WORKDIR /tmp/build
ENV PIP_ROOT_USER_ACTION=ignore

COPY requirements.txt .
RUN python -m pip install --upgrade pip \
 && python -m pip install --no-cache-dir --prefix=/install -r requirements.txt

# Reuse the same Python + Playwright from builder so the versions match.
FROM python:3.13-slim AS browsers
WORKDIR /tmp/browsers

# Minimal runtime libs that Playwright/Chromium need on Debian trixie.
# (We install them here as well so "playwright install chromium" can run.)
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      # common runtime libs
      libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
      libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
      libxrandr2 libgbm1 libpango-1.0-0 libasound2 libatspi2.0-0 \
      libwayland-client0 libwayland-cursor0 libwayland-egl1 \
      libxshmfence1 \
      # fonts (Debian trixie uses fonts-*; ttf-* names are obsolete)
      fonts-liberation fonts-unifont fonts-ubuntu \
 && rm -rf /var/lib/apt/lists/*

# Bring Playwright CLI from builder stage
COPY --from=builder /install /usr/local

# Download Chromium only, into a fixed path we can copy between stages.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN python -m playwright install chromium

FROM python:3.13-slim

ENV TZ=Europe/London \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_ROOT_USER_ACTION=ignore \
    # Tell Playwright where the preinstalled browsers live:
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Install the same runtime libs as in the browsers stage.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
      libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
      libxrandr2 libgbm1 libpango-1.0-0 libasound2 libatspi2.0-0 \
      libwayland-client0 libwayland-cursor0 libwayland-egl1 \
      libxshmfence1 \
      fonts-liberation fonts-unifont fonts-ubuntu \
 && rm -rf /var/lib/apt/lists/*

# Python site-packages (includes Playwright + ics)
COPY --from=builder /install /usr/local

# Chromium binaries (cached)
COPY --from=browsers /ms-playwright /ms-playwright

COPY scrape.py .

# Defaults (override via compose/.env)
ENV OUTPUT_PATH=/output/bins.ics \
    TARGET_URL=https://bnr-wrp.whitespacews.com/#! \
    HEADLESS=1

CMD ["python", "scrape.py"]
