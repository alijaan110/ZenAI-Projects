import time
import json
import re
import os
import logging
from fastapi import FastAPI, HTTPException
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ========== CONFIG ==========
maps_url = "https://maps.app.goo.gl/WxhAxP3hhBcnf6wcA"
chromedriver_path = r"E:\Downloads\chromedriver-win64\chromedriver-win64\chromedriver.exe"
REVIEWS_TO_SCRAPE = 100

logger = logging.getLogger("app")
logging.basicConfig(level=logging.INFO)

app = FastAPI()


def extract_all_reviews(driver):
    """Extract reviews without date - only rating, reviewer, text"""

    reviews = driver.execute_script(r"""
        function extractReviews() {
            const allReviews = [];
            const wrappers = document.querySelectorAll('div.jftiEf');

            wrappers.forEach((wrapper) => {
                const review = {
                    review_id: '',
                    reviewer: '',
                    rating: null,
                    review_text: ''
                };

                // Review ID
                try {
                    const idEl = wrapper.querySelector('[data-review-id]');
                    if (idEl) review.review_id = idEl.getAttribute('data-review-id');
                } catch(e) {}

                // Reviewer Name
                try {
                    const nameEl = wrapper.querySelector('.d4r55');
                    if (nameEl) review.reviewer = nameEl.textContent.trim();
                } catch(e) {}

                // Review Text
                try {
                    const textEl = wrapper.querySelector('.wiI7pd');
                    if (textEl) review.review_text = textEl.textContent.trim();
                } catch(e) {}

                // === EXTRACT RATING ===
                try {
                    const allText = wrapper.textContent;
                    const ratingMatch = allText.match(/(\d+(?:\.\d+)?)\s*\/\s*5/);
                    if (ratingMatch) {
                        review.rating = parseFloat(ratingMatch[1]);
                    }
                } catch(e) {}

                // Fallback: Search spans for X/5 pattern
                if (review.rating === null) {
                    try {
                        const allSpans = wrapper.querySelectorAll('span');
                        for (let span of allSpans) {
                            const text = span.textContent.trim();
                            const match = text.match(/^(\d+(?:\.\d+)?)\s*\/\s*5/);
                            if (match) {
                                review.rating = parseFloat(match[1]);
                                break;
                            }
                        }
                    } catch(e) {}
                }

                allReviews.push(review);
            });

            return allReviews;
        }

        return extractReviews();
    """)

    return reviews


def clean_phone(phone):
    if not phone:
        return ""
    phone = phone.replace("", "").strip()
    return re.sub(r"[^0-9+]", "", phone)


def scrape_reviews(maps_url=maps_url, chromedriver_path=chromedriver_path, REVIEWS_TO_SCRAPE=REVIEWS_TO_SCRAPE):
    # ========== SELENIUM SETUP (HEADLESS MODE) ==========
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in background
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

    service = Service(chromedriver_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 20)

    try:
        print("🌍 Opening Google Maps (headless mode)...")
        driver.get(maps_url)
        time.sleep(5)

        try:
            reject_btn = driver.find_element(By.XPATH, "//button[contains(., 'Reject all')]")
            reject_btn.click()
            time.sleep(1)
        except:
            pass

        print("🏢 Extracting business details...")
        try:
            name_el = wait.until(EC.visibility_of_element_located((By.XPATH, '//h1[contains(@class,"DUwDvf")]')))
            company_name = name_el.text.strip()
        except:
            company_name = "Unknown"

        phone_number = ""
        for sel in ['//button[contains(@aria-label,"Phone")]', '//button[contains(@data-item-id,"phone:tel")]', '//a[contains(@href,"tel:")]']:
            try:
                el = driver.find_element(By.XPATH, sel)
                phone_number = el.text or el.get_attribute("href")
                break
            except:
                continue
        phone_number = clean_phone(phone_number)

        print(f"✔ Company: {company_name}")
        print(f"✔ Phone: {phone_number}")

        print("🟦 Opening reviews section...")
        try:
            review_tab = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[contains(@aria-label,"reviews")]')))
            driver.execute_script("arguments[0].click();", review_tab)
            time.sleep(4)
        except Exception as e:
            print("⚠ Could not open reviews:", e)

        print("🔁 Scrolling to load reviews...")
        scroll_box = wait.until(EC.presence_of_element_located((By.XPATH, '//div[contains(@class,"m6QErb") and contains(@class,"DxyBCb")]')))

        previous_count = 0
        stale_count = 0
        scroll_attempts = 0

        while scroll_attempts < 80:
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_box)
            time.sleep(1.2)

            current_count = len(driver.find_elements(By.XPATH, '//div[contains(@class,"jftiEf")]'))
            print(f"   Loaded: {current_count} reviews...", end='\r')

            if current_count >= REVIEWS_TO_SCRAPE:
                break

            if current_count == previous_count:
                stale_count += 1
                if stale_count >= 5:
                    break
            else:
                stale_count = 0

            previous_count = current_count
            scroll_attempts += 1

        print(f"\n✔ Total reviews loaded: {current_count}")

        print("📝 Extracting reviews...")
        reviews_data = extract_all_reviews(driver)
        reviews_data = reviews_data[:REVIEWS_TO_SCRAPE]

        for review in reviews_data:
            if review['rating'] is not None:
                review['rating'] = str(review['rating'])
            else:
                review['rating'] = "No rating"

        os.makedirs("output", exist_ok=True)
        file_name = re.sub(r'[^A-Za-z0-9 ]+', '', company_name).replace(" ", "_") + "_reviews.json"
        path = os.path.join("output", file_name)

        result = {
            "company_name": company_name,
            "phone_number": phone_number,
            "total_reviews": len(reviews_data),
            "reviews": reviews_data
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4, ensure_ascii=False)

        ratings_found = sum(1 for r in reviews_data if r['rating'] != 'No rating')

        print(f"\n🎉 DONE! Saved to: {path}")
        print(f"\n📊 Statistics:")
        print(f"   Total Reviews: {len(reviews_data)}")
        print(f"   ✓ Ratings Found: {ratings_found}/{len(reviews_data)} ({ratings_found/len(reviews_data)*100:.1f}%)")
        print(f"   ✓ Reviews with Text: {sum(1 for r in reviews_data if r['review_text'])}")

        if reviews_data:
            print(f"\n📝 Sample Reviews:")
            for i in range(min(3, len(reviews_data))):
                print(f"\n   [{i+1}] {reviews_data[i]['reviewer']}")
                print(f"       Rating: {reviews_data[i]['rating']}")
                print(f"       Text: {reviews_data[i]['review_text'][:80]}...")

        return result

    except Exception as e:
        print("❌ ERROR:", e)
        import traceback
        traceback.print_exc()
        raise

    finally:
        driver.quit()


@app.get("/")
@app.post("/")
def scrape_endpoint(maps_url: str = maps_url, chromedriver_path: str = chromedriver_path, REVIEWS_TO_SCRAPE: int = REVIEWS_TO_SCRAPE):
    try:
        return scrape_reviews(maps_url=maps_url, chromedriver_path=chromedriver_path, REVIEWS_TO_SCRAPE=REVIEWS_TO_SCRAPE)
    except Exception as e:
        logger.exception("Unhandled error")
        raise HTTPException(status_code=500, detail=f"❌ ERROR: {e}")
