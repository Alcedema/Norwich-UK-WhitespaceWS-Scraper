FROM python:3.12-slim AS builder
WORKDIR /tmp/build
ENV PIP_ROOT_USER_ACTION=ignore

COPY requirements.txt .
RUN python -m pip install --upgrade pip \
 && python -m pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.12-slim AS browsers
WORKDIR /tmp/browsers

# Minimal runtime libs for Chromium on Debian trixie.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
      libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
      libxrandr2 libgbm1 libpango-1.0-0 libasound2 libatspi2.0-0 \
      libwayland-client0 libwayland-cursor0 libwayland-egl1 \
      libxshmfence1 \
      fonts-liberation fonts-unifont fonts-noto-core \
 && rm -rf /var/lib/apt/lists/*

# Bring playwright (installed in builder) into PATH
COPY --from=builder /install /usr/local

# Download ONLY Chromium; no --with-deps (avoids Ubuntu-specific packages).
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN python -m playwright install chromium


FROM python:3.12-slim

ENV TZ=Europe/London \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Same runtime libs as in the browsers stage
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
      libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
      libxrandr2 libgbm1 libpango-1.0-0 libasound2 libatspi2.0-0 \
      libwayland-client0 libwayland-cursor0 libwayland-egl1 \
      libxshmfence1 \
      fonts-liberation fonts-unifont fonts-noto-core \
 && rm -rf /var/lib/apt/lists/*

# Python deps (playwright + ics) and cached Chromium
COPY --from=builder  /install       /usr/local
COPY --from=browsers /ms-playwright /ms-playwright

COPY scrape.py .

# Defaults (override in compose/.env)
ENV OUTPUT_PATH=/output/bins.ics \
    TARGET_URL=https://bnr-wrp.whitespacews.com/#! \
    HEADLESS=1

CMD ["python", "scrape.py"]
