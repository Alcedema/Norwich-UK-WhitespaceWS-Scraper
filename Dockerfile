FROM mcr.microsoft.com/playwright/python:v1.46.0-jammy AS builder
WORKDIR /tmp/build
ENV PIP_ROOT_USER_ACTION=ignore
COPY requirements.txt .
RUN python -m pip install --upgrade pip \
 && python -m pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Final: slim runtime with deps + your script ----
FROM mcr.microsoft.com/playwright/python:v1.46.0-jammy

ENV TZ=Europe/London \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Bring in only the installed packages from builder
COPY --from=builder /install /usr/local

# App
COPY scrape.py .

# Defaults (override via env/compose)
ENV OUTPUT_PATH=/output/bins.ics \
    TARGET_URL=https://bnr-wrp.whitespacews.com/#! \
    HEADLESS=1

CMD ["python", "scrape.py"]