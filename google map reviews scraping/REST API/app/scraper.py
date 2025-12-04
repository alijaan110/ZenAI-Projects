import time
import re
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    NoSuchElementException
)

class GoogleMapsScraper:
    """
    A class to scrape Google Maps reviews
    """
    
    def __init__(
        self,
        maps_url: str,
        chromedriver_path: str = "/usr/local/bin/chromedriver",
        headless: bool = True,
        wait_timeout: int = 20,
        scroll_pause: float = 1.5,
        max_scrolls: int = 500
    ):
        self.maps_url = maps_url
        self.chromedriver_path = chromedriver_path
        self.headless = headless
        self.wait_timeout = wait_timeout
        self.scroll_pause = scroll_pause
        self.max_scrolls = max_scrolls
        self.driver = None
        self.wait = None
        
    def _setup_driver(self):
        """Initialize Chrome WebDriver with anti-detection settings"""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument("--headless=new")
        
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        
        service = Service(self.chromedriver_path)
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Anti-detection measures
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        })
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        
        self.wait = WebDriverWait(self.driver, self.wait_timeout)
        
    def _close_cookie_popup(self):
        """Close cookie consent popup if present"""
        try:
            reject_btn = self.driver.find_element(
                By.XPATH, 
                "//button[contains(., 'Reject all')]"
            )
            reject_btn.click()
            time.sleep(2)
        except NoSuchElementException:
            pass
        
    def _extract_company_info(self) -> tuple[str, str]:
        """Extract company name and phone number"""
        company_name = ""
        phone_number = ""
        
        # Extract company name
        try:
            name_el = self.wait.until(
                EC.presence_of_element_located((By.XPATH, '//h1[contains(@class,"DUwDvf")]'))
            )
            company_name = name_el.text.strip()
        except TimeoutException:
            print("⚠️ Could not extract company name")
        
        # Try multiple methods to get phone
        phone_candidates = [
            '//button[contains(@aria-label, "Phone")]',
            '//button[contains(@data-item-id, "phone:tel")]',
            '//button[contains(@aria-label, "Call")]',
            '//div[contains(text(), "+") and contains(text(), " ")]',
            '//a[contains(@href,"tel:")]'
        ]
        
        for xpath in phone_candidates:
            try:
                phone_el = self.driver.find_element(By.XPATH, xpath)
                phone_number = phone_el.text.strip()
                if not phone_number:
                    phone_number = phone_el.get_attribute("href") or ""
                    phone_number = phone_number.replace("tel:", "")
                if phone_number:
                    break
            except NoSuchElementException:
                continue
        
        return company_name, phone_number.strip()
    
    def _open_reviews_tab(self):
        """Click on reviews tab to load reviews section"""
        try:
            review_tab = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(@aria-label,"reviews")]'))
            )
            self.driver.execute_script("arguments[0].click();", review_tab)
            time.sleep(4)
        except TimeoutException as e:
            raise Exception(f"Could not open reviews section: {e}")
    
    def _scroll_reviews(self) -> set:
        """Scroll through all reviews and return set of review IDs"""
        scroll_div = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, '//div[contains(@class,"m6QErb") and contains(@class,"DxyBCb")]')
            )
        )
        
        seen_ids = set()
        stale_count = 0
        scroll_count = 0
        max_stale = 6
        
        print("🔁 Scrolling through all reviews...")
        
        while stale_count < max_stale and scroll_count < self.max_scrolls:
            self.driver.execute_script(
                'arguments[0].scrollTop = arguments[0].scrollHeight', 
                scroll_div
            )
            time.sleep(self.scroll_pause)
            
            current_ids = set()
            for el in self.driver.find_elements(By.XPATH, '//div[@data-review-id]'):
                rid = el.get_attribute('data-review-id')
                if rid:
                    current_ids.add(rid)
            
            new_reviews = current_ids - seen_ids
            if new_reviews:
                seen_ids.update(new_reviews)
                stale_count = 0
            else:
                stale_count += 1
            
            scroll_count += 1
            if scroll_count % 10 == 0:
                print(f"   Scroll {scroll_count}: {len(seen_ids)} unique reviews "
                      f"(no new: {stale_count}/{max_stale})")
        
        print(f"✅ Finished scrolling — {len(seen_ids)} total reviews detected.\n")
        return seen_ids
    
    def _expand_see_more(self):
        """Expand all 'See more' buttons to get full review text"""
        print("📖 Expanding 'See more' sections...")
        for btn in self.driver.find_elements(By.XPATH, '//button[@aria-label="See more"]'):
            try:
                self.driver.execute_script("arguments[0].click();", btn)
            except:
                continue
        time.sleep(2)
    
    def _extract_reviews(self, company_name: str, phone_number: str) -> List[Dict]:
        """Extract all review data from page"""
        print("📝 Extracting all reviews...")
        reviews_data = []
        elements = self.driver.find_elements(By.XPATH, '//div[@data-review-id]')
        
        for idx, r in enumerate(elements):
            try:
                review_id = r.get_attribute('data-review-id')
                if not review_id:
                    continue
                
                # Rating
                rating = "No rating"
                try:
                    rating_el = r.find_element(By.XPATH, './/*[contains(@aria-label,"star")]')
                    rating = rating_el.get_attribute("aria-label")
                except NoSuchElementException:
                    pass
                
                # Review Text
                text = ""
                try:
                    text_el = r.find_element(By.XPATH, './/span[@class="wiI7pd"]')
                    text = text_el.text.strip()
                except NoSuchElementException:
                    pass
                
                # Reviewer Name
                reviewer = ""
                try:
                    reviewer_el = r.find_element(By.XPATH, './/div[contains(@class,"d4r55")]')
                    reviewer = reviewer_el.text.strip()
                except NoSuchElementException:
                    pass
                
                # Date
                date = ""
                try:
                    date_el = r.find_element(By.XPATH, './/span[contains(@class,"rsqaWe")]')
                    date = date_el.text.strip()
                except NoSuchElementException:
                    pass
                
                reviews_data.append({
                    "review_id": review_id,
                    "reviewer": reviewer,
                    "rating": rating,
                    "review_text": text,
                    "date": date,
                    "company_name": company_name,
                    "phone_number": phone_number
                })
                
                if (idx + 1) % 100 == 0:
                    print(f"   Processed {idx + 1} reviews...")
                    
            except StaleElementReferenceException:
                continue
            except Exception:
                continue
        
        return reviews_data
    
    def scrape(self) -> List[Dict]:
        """
        Main scraping method
        
        Returns:
            List of dictionaries containing review data
        """
        try:
            self._setup_driver()
            
            print(f"🌐 Opening Google Maps: {self.maps_url}")
            self.driver.get(self.maps_url)
            time.sleep(6)
            
            self._close_cookie_popup()
            
            print("🏢 Extracting company details...")
            company_name, phone_number = self._extract_company_info()
            print(f"✅ Company: {company_name or 'N/A'}")
            print(f"📞 Phone: {phone_number or 'Not found'}\n")
            
            self._open_reviews_tab()
            self._scroll_reviews()
            self._expand_see_more()
            
            reviews_data = self._extract_reviews(company_name, phone_number)
            
            print(f"\n✅ DONE! Extracted {len(reviews_data)} reviews")
            
            return reviews_data
            
        except Exception as e:
            raise Exception(f"Scraping failed: {str(e)}")
        
        finally:
            if self.driver:
                self.driver.quit()