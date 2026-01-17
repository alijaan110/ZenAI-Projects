import logging
import random
import re
import time
from datetime import datetime, timezone
from math import atan2, cos, radians, sin, sqrt
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote_plus, urlparse

import requests
import json
from urllib.parse import unquote
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger("gmaps-scraper")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
]

PHONE_RE = re.compile(r"(\+?\d[\d\-\s\(\)]{6,}\d)")
PLACE_COORD_RE = re.compile(r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)")
AT_COORD_RE = re.compile(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)")
ZOOM_LEVELS = {50: 8, 20: 11, 10: 12, 5: 13, 2: 14, 1: 15}
SHORT_DOMAINS = ("maps.app.goo.gl", "goo.gl", "maps.fi", "goo.gl/maps")


def radius_to_zoom(radius_km: int) -> int:
    for r, z in sorted(ZOOM_LEVELS.items(), reverse=True):
        if radius_km >= r:
            return z
    return 15


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    lat1_rad, lng1_rad = radians(lat1), radians(lng1)
    lat2_rad, lng2_rad = radians(lat2), radians(lng2)

    dlat = lat2_rad - lat1_rad
    dlng = lng2_rad - lng1_rad

    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlng / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return round(r * c, 2)


def parse_coordinates(url: str) -> Tuple[Optional[float], Optional[float]]:
    try:
        place_match = PLACE_COORD_RE.search(url)
        if place_match:
            return float(place_match.group(1)), float(place_match.group(2))
        at_match = AT_COORD_RE.search(url)
        if at_match:
            return float(at_match.group(1)), float(at_match.group(2))
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "ll" in qs:
            lat_s, lng_s = qs["ll"][0].split(",")[:2]
            return float(lat_s), float(lng_s)
    except Exception as exc:
        logger.debug("parse_coordinates error: %s", exc)
    return None, None


def make_search_url(lat: float, lng: float, zoom: int, keyword: Optional[str] = None) -> str:
    k = quote_plus(keyword.strip()) if keyword else "businesses"
    return f"https://www.google.com/maps/search/{k}/@{lat},{lng},{zoom}z"


def safe_sleep(a: float = 0.4, b: float = 1.0) -> None:
    time.sleep(random.uniform(a, b))


def expand_short_url_requests(url: str, timeout: int = 10) -> Optional[str]:
    try:
        logger.info("Expanding short URL: %s", url)
        resp = requests.get(url, timeout=timeout, allow_redirects=True)
        logger.info("Expanded to: %s", resp.url)
        return resp.url
    except Exception as exc:
        logger.debug("Expansion failed: %s", exc)
        return None


def init_driver(headless: bool = False) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("window-size=1400,900")
    options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
    except Exception:
        pass

    logger.info("Chrome driver initialized")
    return driver


def find_results_panel(driver: webdriver.Chrome, timeout: int = 12):
    wait = WebDriverWait(driver, timeout)
    candidates = [
        (By.CSS_SELECTOR, "div[role='feed']"),
        (By.XPATH, "//div[@role='region']//div[contains(@class,'scrollbox')]"),
        (By.XPATH, "//div[contains(@aria-label,'Results') or contains(@aria-label,'results')]"),
        (By.CSS_SELECTOR, "div[role='region']"),
    ]
    for by, sel in candidates:
        try:
            return wait.until(EC.presence_of_element_located((by, sel)))
        except TimeoutException:
            continue
    return None


def get_current_hrefs(driver: webdriver.Chrome) -> List[str]:
    hrefs = []
    for a in driver.find_elements(By.XPATH, "//a[contains(@href,'/maps/place/')]"):
        href = a.get_attribute("href")
        if href:
            hrefs.append(href)
    return list(dict.fromkeys(hrefs))


def extract_from_place_url(
    driver: webdriver.Chrome, href: str, center_lat: float, center_lng: float
) -> Dict:
    result = {
        "business_name": "N/A",
        "address": "N/A",
        "category": "N/A",
        "rating": "N/A",
        "reviews_count": "0",
        "google_maps_url": href,
        "company_url": "N/A",
        "phone": "N/A",
        "opening_hours": [],
        "price_level": "N/A",
        "attributes": [],
        "images": [],
        "description": "N/A",
        "latitude": None,
        "longitude": None,
        "distance_km": None,
        "raw_page_text_snippet": "",
    }

    business_lat, business_lng = parse_coordinates(href)
    if business_lat and business_lng:
        result["latitude"] = business_lat
        result["longitude"] = business_lng
        result["distance_km"] = haversine_distance(
            center_lat, center_lng, business_lat, business_lng
        )

    original_window = driver.current_window_handle
    driver.execute_script("window.open(arguments[0], '_blank');", href)
    safe_sleep(0.6, 1.2)

    windows = driver.window_handles
    new_window = [w for w in windows if w != original_window][-1]
    driver.switch_to.window(new_window)

    try:
        WebDriverWait(driver, 12).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        safe_sleep(1.0, 2.0)

        page_text = driver.page_source.lower()
        if "unusual traffic" in page_text or "are you a robot" in page_text:
            logger.error("Captcha detected")
            raise RuntimeError("Captcha detected")

        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Try to extract coordinates, opening hours, company url and price from JSON-LD first
        try:
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    jd = json.loads(script.string or script.get_text())
                except Exception:
                    continue

                # jd may be a list or dict
                items = jd if isinstance(jd, list) else [jd]
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    # Geo coordinates
                    geo = it.get("geo") or it.get("location", {}).get("geo")
                    if geo and isinstance(geo, dict):
                        lat_j = geo.get("latitude") or geo.get("lat")
                        lng_j = geo.get("longitude") or geo.get("lng")
                        try:
                            if lat_j and lng_j and (not result["latitude"] or not result["longitude"]):
                                result["latitude"] = float(lat_j)
                                result["longitude"] = float(lng_j)
                                result["distance_km"] = haversine_distance(
                                    center_lat, center_lng, result["latitude"], result["longitude"]
                                )
                        except Exception:
                            pass

                    # Company website/url
                    if result["company_url"] == "N/A":
                        url_field = it.get("url") or it.get("mainEntityOfPage") or it.get("sameAs")
                        if isinstance(url_field, list) and url_field:
                            result["company_url"] = url_field[0]
                        elif isinstance(url_field, str) and url_field:
                            result["company_url"] = url_field

                    # Opening hours
                    if not result["opening_hours"]:
                        oh = it.get("openingHoursSpecification") or it.get("openingHours")
                        if isinstance(oh, list):
                            hrs = []
                            for o in oh:
                                if isinstance(o, dict):
                                    day = o.get("dayOfWeek") or o.get("day")
                                    opens = o.get("opens") or o.get("openingTime")
                                    closes = o.get("closes") or o.get("closingTime")
                                    if day and opens and closes:
                                        hrs.append(f"{day}: {opens} - {closes}")
                            if hrs:
                                result["opening_hours"] = hrs
                        elif isinstance(oh, str):
                            # openingHours sometimes is a single string
                            result["opening_hours"] = [oh]

                    # Price range
                    if result["price_level"] == "N/A":
                        pr = it.get("priceRange") or it.get("price")
                        if pr:
                            result["price_level"] = str(pr)

                # break early if we have some data
                if result["latitude"] and (result["company_url"] != "N/A" or result["opening_hours"]):
                    break

        except Exception:
            pass

        # Fallback: parse coords from current URL if JSON-LD didn't provide them
        if not result["latitude"] or not result["longitude"]:
            current_url = driver.current_url
            business_lat, business_lng = parse_coordinates(current_url)
            if business_lat and business_lng:
                result["latitude"] = business_lat
                result["longitude"] = business_lng
                result["distance_km"] = haversine_distance(
                    center_lat, center_lng, business_lat, business_lng
                )

        # Extra fallback: try to extract coords from page JSON blobs if still missing
        if not result["latitude"] or not result["longitude"]:
            page_text = driver.page_source
            # look for patterns like "latitude":25.123 or "lat":25.123
            m = re.search(r'"latitude"\s*[:=]\s*([\d\.-]+)', page_text)
            n = re.search(r'"longitude"\s*[:=]\s*([\d\.-]+)', page_text)
            if m and n:
                try:
                    lat_j = float(m.group(1))
                    lng_j = float(n.group(1))
                    result["latitude"] = lat_j
                    result["longitude"] = lng_j
                    result["distance_km"] = haversine_distance(center_lat, center_lng, lat_j, lng_j)
                except Exception:
                    pass
            else:
                # try "lat":25.12, "lng":55.12 or "center":[25.12,55.12]
                m2 = re.search(r'"lat"\s*[:=]\s*([\d\.-]+).*?"lng"\s*[:=]\s*([\d\.-]+)', page_text, re.S)
                if m2:
                    try:
                        lat_j = float(m2.group(1))
                        lng_j = float(m2.group(2))
                        result["latitude"] = lat_j
                        result["longitude"] = lng_j
                        result["distance_km"] = haversine_distance(center_lat, center_lng, lat_j, lng_j)
                    except Exception:
                        pass
                else:
                    m3 = re.search(r'"center"\s*[:=]\s*\[\s*([\d\.-]+)\s*,\s*([\d\.-]+)\s*\]', page_text)
                    if m3:
                        try:
                            lat_j = float(m3.group(1))
                            lng_j = float(m3.group(2))
                            result["latitude"] = lat_j
                            result["longitude"] = lng_j
                            result["distance_km"] = haversine_distance(center_lat, center_lng, lat_j, lng_j)
                        except Exception:
                            pass

        # Fallback extraction for opening hours from page text if still empty
        if not result["opening_hours"]:
            page_text = driver.page_source
            day_pattern = r"(Mon|Monday|Tue|Tuesday|Wed|Wednesday|Thu|Thursday|Fri|Friday|Sat|Saturday|Sun|Sunday)\w*[^<>\n\r]{0,100}"
            matches = re.findall(day_pattern, page_text, flags=re.IGNORECASE)
            if matches:
                # find lines containing day names and nearby times
                lines = []
                for m in re.finditer(r"([A-Za-z]{3,9}[^<>\n\r]{0,80})", page_text):
                    t = m.group(1).strip()
                    if re.search(r"Mon|Tue|Wed|Thu|Fri|Sat|Sun|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday", t, re.IGNORECASE) and re.search(r"\d{1,2}:\d{2}|am|pm", t, re.IGNORECASE):
                        lines.append(t)
                if lines:
                    # dedupe and limit
                    seen = []
                    for l in lines:
                        if l not in seen:
                            seen.append(l)
                    result["opening_hours"] = seen[:7]

        h1 = soup.select_one("h1")
        if h1 and h1.get_text(strip=True):
            result["business_name"] = h1.get_text(strip=True)

        addr = None
        cand = soup.select_one(
            "button[data-item-id='address'] .Io6YTe, span[data-item-id='address'], "
            "div[aria-label*='Address']"
        )
        if cand and cand.get_text(strip=True):
            addr = cand.get_text(strip=True)
        else:
            cand2 = soup.select_one("div[data-tooltip='Copy address'], div[data-item-id='address']")
            if cand2 and cand2.get_text(strip=True):
                addr = cand2.get_text(strip=True)
        if addr:
            result["address"] = addr

        cat_candidates = [
            "button[jsaction*='pane.rating.category']",
            "button[data-item-id='entity-category']",
            "div[data-item-id='subtitle']",
            "span.fontBodySmall",
        ]
        for selector in cat_candidates:
            cat = soup.select_one(selector)
            if cat and cat.get_text(strip=True):
                cat_text = cat.get_text(strip=True)
                if not re.search(
                    r"\b(today|yesterday|\d+\s+(?:day|days|hour|hours|minute|minutes)\s+ago)\b",
                    cat_text.lower(),
                ):
                    result["category"] = cat_text
                    break
        if result["category"] == "N/A":
            text_flat = soup.get_text(" ", strip=True)
            cat_match = re.search(
                r"\b\d\.\d\b\s*\(\s*[\d,]+\s*\)\s*([^·•]{2,60})\s*[·•]",
                text_flat,
            )
            if cat_match:
                cat_text = cat_match.group(1).strip()
                if (
                    len(cat_text) <= 60
                    and "review" not in cat_text.lower()
                    and "rating" not in cat_text.lower()
                ):
                    result["category"] = cat_text

        rating_found = False
        for div in soup.find_all("div", {"aria-label": True}):
            aria_label = div.get("aria-label", "").lower()
            if "star" in aria_label or "rating" in aria_label:
                rating_match = re.search(r"(\d+\.?\d*)\s*(?:star|out)", aria_label)
                if rating_match:
                    result["rating"] = rating_match.group(1)
                    rating_found = True
                    break

        if not rating_found:
            rating_span = soup.find(
                "span", {"aria-hidden": "true"}, string=re.compile(r"^\d+\.\d+$")
            )
            if rating_span:
                result["rating"] = rating_span.get_text(strip=True)
                rating_found = True

        reviews_found = False
        for button in soup.find_all("button"):
            btn_text = button.get_text(" ", strip=True)
            if "review" in btn_text.lower():
                review_match = re.search(r"(\d[\d,]*)\s*review", btn_text.lower())
                if review_match:
                    result["reviews_count"] = review_match.group(1).replace(",", "")
                    reviews_found = True
                    break

        if not reviews_found:
            for elem in soup.find_all(attrs={"aria-label": True}):
                aria = elem.get("aria-label", "")
                if "review" in aria.lower():
                    review_match = re.search(r"(\d[\d,]*)\s*review", aria.lower())
                    if review_match:
                        result["reviews_count"] = review_match.group(1).replace(",", "")
                        break

        for a in soup.find_all("a", href=True):
            href_a = a["href"]
            # Handle relative Google redirect links like /url?q=...
            if href_a.startswith("/url") or "google.com/url" in href_a:
                parsed = urlparse(href_a)
                target = parse_qs(parsed.query).get("q", [None])[0]
                if not target:
                    # try to extract q= from the path
                    m = re.search(r"/url\?q=([^&]+)", href_a)
                    if m:
                        target = unquote(m.group(1))
                if target:
                    tgt = target
                    if isinstance(tgt, str) and "google" not in tgt and "/maps" not in tgt:
                        result["company_url"] = tgt
                        break

            # Direct external link
            if href_a.startswith("http"):
                if "google" not in href_a and "/maps" not in href_a:
                    result["company_url"] = href_a
                    break

        if result["company_url"] == "N/A":
            auth = soup.select_one("a[data-item-id='authority'], a[aria-label*='Website']")
            if auth and auth.get("href"):
                href_auth = auth.get("href")
                if href_auth.startswith("/url"):
                    parsed = urlparse(href_auth)
                    q = parse_qs(parsed.query).get("q", [None])[0]
                    if q:
                        result["company_url"] = unquote(q)
                    else:
                        result["company_url"] = href_auth
                else:
                    result["company_url"] = href_auth

        ph = None
        phone_btn = soup.select_one(
            "button[aria-label*='Call'], a[aria-label*='Call'], "
            "button[data-item-id='phone'], button[data-tooltip*='phone']"
        )
        if phone_btn:
            text = phone_btn.get_text(" ", strip=True)
            match = PHONE_RE.search(text)
            if match:
                ph = match.group(1)
        if not ph:
            text_all = soup.get_text(" ")
            match = PHONE_RE.search(text_all)
            if match:
                ph = match.group(1)
        if ph:
            result["phone"] = ph

        hours = []
        hours_parent = (
            soup.select_one("table[class*='WgFkxc']")
            or soup.select_one("div[aria-label*='Hours']")
            or soup.select_one("div[data-item-id='hours']")
        )
        if hours_parent:
            for tr in hours_parent.select("tr"):
                txt = tr.get_text(" ", strip=True)
                if txt:
                    hours.append(txt)
        else:
            for li in soup.select("div.section-open-hours, div[jsinstance] li"):
                t = li.get_text(" ", strip=True)
                if t and any(day in t.lower() for day in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]):
                    hours.append(t)
        if hours:
            result["opening_hours"] = hours

        txt_all = soup.get_text(" ")
        # Try currency symbols and explicit ranges first
        price_m = re.search(r"(\u00a3|\$|\u20ac|AED)\s*\d+[\s–\-]*\d*", txt_all, re.IGNORECASE)
        if price_m:
            result["price_level"] = price_m.group(0)
        else:
            # common shorthand like $, $$, AED ranges or words
            match2 = re.search(r"(\${1,4}|\u00a3{1,4}|\u20ac{1,4}|AED\s*\d+|\bAED\b)", txt_all, re.IGNORECASE)
            if match2:
                result["price_level"] = match2.group(0)

        attrs = []
        for sp in soup.select("button[jsaction*='pane.placeActions'], span[class*='ucwH6d'], div.fontBodySmall"):
            t = sp.get_text(" ", strip=True)
            if t and len(t) < 60:
                attrs.append(t)
        result["attributes"] = list(dict.fromkeys([a for a in attrs if a and len(a) > 0]))[:12]

        images = []
        for img in soup.select("img[src]"):
            src = img.get("src", "")
            if src and len(src) > 30:
                images.append(src)
        result["images"] = images[:10]

        desc_candidate = soup.select_one("div[data-section-id='overview'], div[data-item-id='description']")
        if desc_candidate and desc_candidate.get_text(strip=True):
            result["description"] = desc_candidate.get_text(" ", strip=True)
        else:
            long_texts = [
                p.get_text(" ", strip=True)
                for p in soup.select("div")
                if p.get_text(strip=True) and 40 < len(p.get_text(strip=True)) < 600
            ]
            if long_texts:
                result["description"] = long_texts[0]

        result["raw_page_text_snippet"] = soup.get_text(" ", strip=True)[:800]

    except Exception as exc:
        logger.warning("Error extracting %s: %s", href, exc)
    finally:
        try:
            driver.close()
        except Exception:
            pass
        try:
            driver.switch_to.window(original_window)
        except Exception:
            try:
                driver.switch_to.window(driver.window_handles[0])
            except Exception:
                pass

    return result


def scrape_area(
    input_url: str,
    radius_km: int = 5,
    keyword: Optional[str] = None,
    desired_results: int = 10,
    headless: bool = False,
) -> Dict:
    input_url = input_url.strip()
    full_url = input_url

    parsed = urlparse(input_url)
    domain = parsed.netloc.lower()
    if any(d in domain for d in SHORT_DOMAINS):
        expanded = expand_short_url_requests(input_url)
        if expanded:
            full_url = expanded

    lat, lng = parse_coordinates(full_url)

    driver = init_driver(headless=headless)
    try:
        if lat is None or lng is None:
            logger.info("Resolving URL via browser...")
            driver.get(full_url)
            safe_sleep(2.0, 3.0)
            full_url = driver.current_url
            lat, lng = parse_coordinates(full_url)

        if lat is None or lng is None:
            raise ValueError("Could not parse coordinates from URL")

        zoom = radius_to_zoom(radius_km)

        if "/place/" in full_url and not keyword:
            search_url = make_search_url(lat, lng, zoom, None)
        else:
            if keyword:
                search_url = make_search_url(lat, lng, zoom, keyword)
            else:
                if "/search/" in full_url or "@" in full_url:
                    search_url = full_url
                else:
                    search_url = make_search_url(lat, lng, zoom, None)

        logger.info("Opening search URL: %s", search_url)
        driver.get(search_url)
        safe_sleep(2.0, 3.5)

        if "unusual traffic" in driver.page_source.lower():
            raise RuntimeError("Captcha detected. Aborting.")

        panel = find_results_panel(driver, timeout=12)

        within_radius = []
        outside_radius = []
        processed_hrefs = set()

        max_scroll_attempts = 100
        scroll_attempts = 0
        no_new_results_count = 0

        while len(within_radius) < desired_results and scroll_attempts < max_scroll_attempts:
            current_hrefs = get_current_hrefs(driver)
            new_hrefs = [h for h in current_hrefs if h not in processed_hrefs]

            if not new_hrefs:
                if panel:
                    try:
                        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", panel)
                    except Exception:
                        driver.execute_script("window.scrollBy(0, window.innerHeight);")
                else:
                    driver.execute_script("window.scrollBy(0, window.innerHeight);")

                safe_sleep(1.0, 1.5)
                scroll_attempts += 1
                no_new_results_count += 1

                if no_new_results_count >= 5:
                    logger.info("No more results available on the page")
                    break

                continue

            no_new_results_count = 0

            for href in new_hrefs:
                if len(within_radius) >= desired_results:
                    break

                processed_hrefs.add(href)
                logger.info(
                    "Processing: %s [Need %d more results]",
                    href[:80],
                    desired_results - len(within_radius),
                )

                try:
                    info = extract_from_place_url(driver, href, lat, lng)

                    if info.get("distance_km") is not None:
                        if info["distance_km"] <= radius_km:
                            within_radius.append(info)
                            logger.info(
                                "[INCLUDED #%d] %s - %.2f km",
                                len(within_radius),
                                info["business_name"],
                                info["distance_km"],
                            )
                        else:
                            outside_radius.append(info)
                            logger.info(
                                "[EXCLUDED] %s - %.2f km (outside radius)",
                                info["business_name"],
                                info["distance_km"],
                            )
                    else:
                        within_radius.append(info)
                        logger.warning(
                            "[INCLUDED #%d] %s - distance unknown",
                            len(within_radius),
                            info["business_name"],
                        )

                    safe_sleep(0.8, 1.8)

                except RuntimeError as exc:
                    logger.error("Aborting due to: %s", exc)
                    break
                except Exception as exc:
                    logger.warning("Failed to extract %s: %s", href, exc)
                    safe_sleep(0.5, 1.0)
                    continue

        within_radius.sort(
            key=lambda x: x.get("distance_km") if x.get("distance_km") is not None else 999
        )

        output = {
            "input_url": input_url,
            "resolved_url": full_url,
            "search_url": search_url,
            "radius_km": radius_km,
            "coordinates": {"lat": lat, "lng": lng},
            "zoom_level": zoom,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "desired_results": desired_results,
            "total_processed": len(processed_hrefs),
            "within_radius": len(within_radius),
            "excluded_outside_radius": len(outside_radius),
            "data": within_radius,
            "excluded_data": outside_radius,
        }

        logger.info("=" * 70)
        logger.info("SUMMARY:")
        logger.info("  Desired results: %d", desired_results)
        logger.info("  Results within %d km: %d", radius_km, len(within_radius))
        logger.info("  Total links processed: %d", len(processed_hrefs))
        logger.info("  Excluded (outside radius): %d", len(outside_radius))
        logger.info("=" * 70)

        return output

    finally:
        try:
            driver.quit()
        except Exception:
            pass
