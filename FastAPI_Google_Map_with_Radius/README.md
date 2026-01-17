# FastAPI Google Map With Radius

Production-grade README for developers and users to download, run, and deploy the application.

## Overview

- Purpose: provide an API that expands a Google Maps short URL or search center and returns nearby businesses within a radius. The project scrapes Google Maps results using Selenium + ChromeDriver and normalizes results (coordinates, opening hours, price, website, distance).
- Stack: Python 3.12, FastAPI, Uvicorn, Selenium (webdriver-manager + ChromeDriver), BeautifulSoup, requests, anyio.

## Repository Layout

- `main.py` — FastAPI application entrypoint.
- `app/routers/scraper.py` — `/api/scrape` endpoint implementation.
- `app/services/scraper.py` — scraping logic using Selenium + BeautifulSoup.
- `app/schemas/scraper.py` — Pydantic models for request/response.
- `requirements.txt` — Python dependencies.

## Quick Start (Local Development)

Prerequisites:
- Python 3.11+ (3.12 recommended)
- Git
- Chrome browser installed (matching version for ChromeDriver)

Steps:

1. Clone the repo:

```bash
git clone <repo-url> FastAPI_Google_Map_with_Radius
cd FastAPI_Google_Map_with_Radius
```

2. Create and activate a virtual environment (Windows):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

4. Start the server (development):

```powershell
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

5. Open the API docs in your browser:

```
http://127.0.0.1:8000/docs
```

Notes:
- If the application immediately shuts down after handling `/api/scrape`, see Troubleshooting below (the scraper uses Selenium which can raise exceptions causing the app to exit).
- For repeated development runs, use `--reload` (not recommended when running Selenium in the same process).

## Running the included test script

The `tools/test_scrape.py` script runs an in-process POST to `/api/scrape` using FastAPI's `TestClient`. It can be useful to run scrapes without exposing the server publicly.

```powershell
.venv\Scripts\python.exe tools/test_scrape.py
```

## API Reference

POST /api/scrape

Description: Given a Google Maps short URL or a search center coordinates, scrapes nearby businesses of the specified type within the given radius and returns normalized results.

Request JSON (example):

```json
{
  "maps_url": "https://maps.app.goo.gl/uKRxBSeEfUCJS1Sp6",
  "radius_km": 10,
  "place_type": "restaurant",
  "desired_results": 5,
  "headless": true
}
```

Fields:
- `maps_url` (string): short URL or Google Maps URL to expand and use as the search center.
- `radius_km` (number): radius in kilometers for inclusion.
- `place_type` (string): place type used in the Google Maps search (e.g., `restaurant`, `cafe`).
- `desired_results` (int): how many matching results to return.
- `headless` (bool): whether Chrome runs in headless mode (recommended for CI/servers).

Response JSON (example):

```json
{
  "request": { ... },
  "results": [
    {
      "name": "Example Restaurant",
      "address": "...",
      "latitude": 25.2354,
      "longitude": 55.3068,
      "distance_km": 3.12,
      "opening_hours": ["Mon: 09:00-22:00", "Tue: 09:00-22:00"],
      "price_level": "AED 50-100",
      "company_url": "https://example.com",
      "rating": 4.3,
      "reviews": 125
    }
  ]
}
```

Notes on fields:
- `opening_hours`: scraper attempts JSON-LD extraction first, with fallback heuristics that parse visible text. Values can be noisy when Google inserts embedded HTML.
- `company_url`: the code attempts to unwrap Google redirect links (`/url?q=...`) and provide direct external URLs when available.
- `distance_km`: computed using a haversine implementation from the place coordinates and the search center.

## Configuration

- `headless`: set to `false` during development to watch the Chrome driver; set to `true` in CI or headless environments.
- ChromeDriver: `webdriver-manager` is used to download and manage the correct binary automatically.

## Deployment Recommendations

- For production, containerize the app.
- Run Selenium in a separate service or use a managed scraping solution: running headless Chrome inside the same uvicorn process can be fragile under load.
- Use process supervisors (systemd, Docker restart policies) to keep the app running.

Example Dockerfile (starter):

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Notes:
- You will need to add Chrome and ChromeDriver to the image if you intend to run Selenium inside the container. Consider running Selenium Grid or a separate Chrome service for reliability.

## Troubleshooting

- If the server shuts down after a `/api/scrape` request, capture the traceback (the Selenium driver can raise `invalid session id` or `no such window` if Chrome crashes). Re-run the server in a terminal to see logs.
- If `/docs` returns `ERR_CONNECTION_REFUSED`, confirm the server is running:

```powershell
tasklist | findstr python
netstat -ano | findstr ":8000"
```

- If ChromeDriver errors occur, make sure your local Chrome version matches the driver downloaded by `webdriver-manager`. The project uses `webdriver-manager` to automatically download a suitable binary, but on some systems manual driver installation may be required.

## Security and Legal

- This project scrapes Google Maps pages. Be aware of terms of service for Google and ensure you have a legal basis for scraping. Consider using official Google APIs when appropriate.

## Contributing

- Open issues and PRs are welcome. Focus areas: robust parsing of opening hours, normalization of price fields, error-handling around Selenium crashes, and adding unit/integration tests.

---