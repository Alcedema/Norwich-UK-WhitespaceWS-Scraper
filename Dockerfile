FROM mcr.microsoft.com/playwright/python:v1.46.0-jammy

# Keep times/dates consistent with the bin schedule
ENV TZ=Europe/London \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && playwright install --with-deps

# App
COPY scrape.py .

# Default output path inside container (bind-mount /output)
ENV OUTPUT_PATH=/output/bins.ics \
    TARGET_URL=https://bnr-wrp.whitespacews.com/#! \
    HEADLESS=1

# Run
CMD ["python", "scrape.py"]
