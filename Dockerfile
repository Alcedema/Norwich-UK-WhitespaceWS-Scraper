FROM python:3.12-slim AS builder
WORKDIR /tmp/build
ENV PIP_ROOT_USER_ACTION=ignore

COPY requirements.txt .
RUN python -m pip install --upgrade pip \
 && python -m pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim

ENV TZ=Europe/London \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl fonts-liberation \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

RUN python -m playwright install --with-deps chromium

COPY scrape.py .

ENV OUTPUT_PATH=/output/bins.ics \
    TARGET_URL=https://bnr-wrp.whitespacews.com/#! \
    HEADLESS=1

CMD ["python", "scrape.py"]
