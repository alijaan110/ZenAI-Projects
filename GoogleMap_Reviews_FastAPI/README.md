# GoogleMap Reviews Scraper (FastAPI + Selenium)

A lightweight FastAPI application that scrapes Google Maps reviews using Selenium (Chrome/Chromedriver). The app exposes a synchronous GET endpoint at `/` which triggers the scraper and returns the scraped reviews as JSON while also saving them to the `output/` folder.

**Status:** Minimal, synchronous scraper. The GET endpoint blocks while Selenium runs. See "Production Notes" for recommended improvements.

**Table of contents**
- About
- Workflow
- Prerequisites
- Installation
- Configuration
- Running (development)
- Running (production)
- Output & Logs
- Troubleshooting
- Security & Notes
- Contributing

## About

This repository contains a FastAPI wrapper around a Selenium-based scraper that visits a Google Maps link, opens the reviews panel, scrolls to load reviews, extracts reviewer name, rating and review text, and writes the data to a JSON file.

The scraper is intended for ad-hoc usage and research. It is not optimized for large-scale scraping or distribution — consult Google Maps Terms of Service before running at scale.

## Workflow

- Start the FastAPI server (it exposes a single GET `/` endpoint by default).
- A request to `/` calls the `scrape_reviews` function in `main.py`.
- Selenium (headless Chrome) opens the provided `maps_url`, navigates to reviews, scrolls to load items, and executes in-page JavaScript to extract review details.
- The app saves the output into an `output/` folder as `<Company_Name>_reviews.json` and returns the same JSON in the response.

## Prerequisites

- Windows or Linux machine with recent Python 3.10+ (project tested with Python 3.12 in this repo).
- Google Chrome or Chromium installed.
- Chromedriver matching the installed Chrome version. Place it somewhere accessible and update `chromedriver_path` in `main.py`.
- Recommended: Create a Python virtual environment for isolation.

## Installation

1. Clone or open the repository.
2. Create and activate a virtual environment (Windows example):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1     # or use activate.bat in cmd
```

3. Install dependencies:

```powershell
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

4. Confirm Chromedriver path in `main.py` (`chromedriver_path` constant) points to the correct `chromedriver.exe` for your Chrome version.

## Configuration

- `maps_url` — default Maps short URL. You can override it by passing a query parameter to `/`.
- `chromedriver_path` — absolute path to `chromedriver.exe` on Windows.
- `REVIEWS_TO_SCRAPE` — default maximum number of reviews to collect.

These values live near the top of `main.py` and can be changed directly or passed as query parameters to the GET endpoint:

Example: `http://127.0.0.1:8000/?maps_url=<URL>&REVIEWS_TO_SCRAPE=20`

## Running (development)

Start the server using `uvicorn` from the project virtual environment (example used in this repo):

```powershell
.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Open the automatic docs at `http://127.0.0.1:8000/docs` to see the available endpoint. Note: the listed GET endpoint will trigger the synchronous scraping operation.

To trigger a scrape from the CLI:

```powershell
curl "http://127.0.0.1:8000/"
```

This will block until the Selenium run completes, return the JSON result, and write `output/<Company>_reviews.json`.

## Running (production)

Recommendations for production:

- Do NOT use the synchronous GET in production for heavy or concurrent loads. Instead:
  - Add an asynchronous POST endpoint that validates input and delegates the scraping to a background thread or task queue (Redis + RQ/Celery/Prefect).
  - Use `asyncio.to_thread()` to run `scrape_reviews` off the event loop if you want a quick improvement.
- Run with a process manager (systemd/Windows service) and a proper ASGI server configuration (e.g. `uvicorn` or `gunicorn` + `uvicorn.workers.UvicornWorker`) with multiple workers if necessary.

Example production run (single host):

```powershell
.
# With multiple workers using gunicorn + uvicorn workers (Linux example):
gunicorn -k uvicorn.workers.UvicornWorker -w 4 main:app
```

## Output & Logs

- Scraped JSON files are saved to `output/` as `<Company_Name>_reviews.json`.
- The app logs to stdout; capture logs with your process manager for persistence.

## Troubleshooting

- Chromedriver mismatch: If Selenium fails to start or crashes, ensure that the Chromedriver version exactly matches the installed Chrome major version. You can check Chrome version by opening `chrome://version/`.
- Headless issues: If pages behave differently in headless mode, try removing `--headless` from `chrome_options` temporarily to observe the browser.
- Permissions: Ensure the process has read/execute permission for `chromedriver.exe` and write permission for `output/`.
- Timeouts: The scraper uses waits and sleeps; if network or page changes cause failures, increase `WebDriverWait` timeouts and sleep pauses in `main.py`.

## Security & Legal Notes

- Respect robots and terms of service. Scraping Google Maps may violate Google's terms; use responsibly.
- Do not expose the scraping endpoint publicly without proper rate limiting and authentication.

## Contributing

- Feel free to open issues or PRs for bug fixes or enhancements. Suggested enhancements:
  - Add a POST endpoint with request validation and background job processing.
  - Add retries and exponential backoff for page loads.
  - Add unit tests and refactor scraping logic into smaller, testable functions.

## License

This project is provided as-is. Add a license file if you plan to share publicly.
