# The need..

Norwich City Council moved to WhitespaceWS to fulfil their waste services and took down the old map logic

# To use..

```
cp .env.example .env   # edit values
docker compose build
docker compose run --rm scraper
# bins.ics -> ./output/bins.ics
```
