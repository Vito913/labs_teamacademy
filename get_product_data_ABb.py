import logging
import random
import time
import csv
from typing import TypedDict
from bs4 import BeautifulSoup, Tag
from attr import dataclass
from seleniumbase import DriverContext
from selenium.webdriver.common.by import By
import pandas as pd
from itertools import zip_longest

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class Review(TypedDict):
    rating: float
    text: str
    translated_text: bool
    response_text: str | None


@dataclass
class AlibabaProduct:
    title: str
    key_attributes: dict[str, str]
    price: dict[str, str]
    reviews: list[Review]
    lead_time: dict[str, str]


class AliBabaScraper:
    def __init__(
        self,
        headless: bool = True,
        load_images: bool = False,
        window_size: tuple[int, int] = (700, 900),
        max_retries: int = 3,
        ud: bool = False,
    ):
        """Initialize scraper with proxy rotation"""
        self.headless = headless
        self.block_images = not load_images
        self.window_size = f"{window_size[0]},{window_size[1]}"
        self.max_retries = max_retries
        self.ud = ud
        self.proxies = self._load_proxies()
        self.current_proxy_index = 0
        logger.debug(f"Loaded {len(self.proxies)} proxies")

        logger.debug(f"Initializing Scraper - Headless: {headless}")

    def _load_proxies(self) -> list[str]:
        """Load proxies from CSV file"""
        try:
            proxies = []
            with open('working_proxies.csv', 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    proxies.append(row['Proxy'])
            return proxies
        except Exception as e:
            logger.error(f"Failed to load proxies: {e}")
            return []

    def _get_next_proxy(self) -> str | None:
        """Get next proxy from the list"""
        if not self.proxies:
            return None
        proxy = self.proxies[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        return proxy

    def __enter__(self):
        logger.debug("Creating new driver instance")
        self._create_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logger.debug("Cleaning up driver")
        if hasattr(self, "driver_context"):
            self.driver_context.__exit__(exc_type, exc_val, exc_tb)
            delattr(self, "driver_context")
            delattr(self, "driver")

    def _create_driver(self, proxy: str | None = None):
        """Create a new driver instance with optional proxy"""
        if proxy:
            logger.debug(f"Creating driver with proxy: {proxy}")
        
        self.driver_context = DriverContext(
            browser="chrome",  # Explicitly set browser
            headless=self.headless,  # Pass headless flag
            block_images=self.block_images,
            window_size=self.window_size,
            uc=self.ud,
            proxy=proxy
        )

        self.driver = self.driver_context.__enter__()

        # Verify browser visibility
        if not self.headless:
            self.driver.maximize_window()
            logger.debug("Browser window maximized")
        return self

    def get(self, url: str) -> bool:

        logger.debug(f"Navigating to: {url}")
        
        # First try without proxy
        try:
            self.driver.get(url)
            if "captcha" not in self.driver.page_source.lower():
                logger.debug("Page loaded successfully without proxy")
                return True
        except Exception as e:
            logger.error(f"Error loading page without proxy: {str(e)}")

        # If failed, try with proxies
        for attempt in range(self.max_retries):
            proxy = self._get_next_proxy()
            if not proxy:
                logger.error("No proxies available")
                return False

            try:
                logger.debug(f"Attempt {attempt + 1} with proxy {proxy}")
                # Clean up existing driver
                if hasattr(self, "driver_context"):
                    self.driver_context.__exit__(None, None, None)
                
                # Create new driver with proxy
                self._create_driver(proxy=proxy)
                self.driver.get(url)
                
                if "captcha" not in self.driver.page_source.lower():
                    logger.debug(f"Page loaded successfully with proxy {proxy}")
                    return True
                    
            except Exception as e:
                logger.error(f"Error with proxy {proxy}: {str(e)}")

        logger.error("Failed to load page with all available proxies")
        return False

    def accept_cookies_ex(self):
        try:
            time.sleep(2)  # Initial wait for the cookie popup
            # Using the improved Driver methods
            cookie_agree = self.driver.find_element(
                "div.gdpr-footer div.gdpr-agree-btn"
            )
            if cookie_agree:
                cookie_agree.click()
                logger.debug("Cookies accepted successfully")
                return True
        except Exception as e:
            logger.error(f"Failed to accept cookies: {e}")
            return False


def extract_title(soup: BeautifulSoup) -> str:
    title_element = soup.find("h1")
    return title_element.text.strip() if title_element else "Title not found"


def extract_key_attributes(soup: BeautifulSoup) -> dict[str, str]:
    key_attributes = {}
    try:
        attribute_items = soup.select("div.attribute-item")
        for item in attribute_items:
            key = item.select_one("div.left")
            value = item.select_one("div.right")
            if key and value:
                key_attributes[key.text.strip()] = value.text.strip()
    except Exception as e:
        logger.warning(f"Failed to extract key attributes: {e}")
    return key_attributes


def extract_lead_time(soup: BeautifulSoup) -> dict[str, str]:
    lead_time = {}
    try:
        lead_table = soup.select_one("div.lead-layout table")
        if lead_table:
            rows = lead_table.select("tr")
            if len(rows) >= 2:
                quantities = rows[0].select("td")[1:]
                times = rows[1].select("td")[1:]
                for qty, time_to_deliver in zip(quantities, times):
                    lead_time[qty.text.strip()] = time_to_deliver.text.strip()
    except Exception as e:
        logger.warning(f"Failed to extract lead time: {e}")
    return lead_time


def extract_price(soup: BeautifulSoup) -> dict[str, str]:
    price_dict = {}
    try:
        price_items = soup.select("div.module_price div.price-item")
        for item in price_items:
            quantity = item.select_one("div.quality")
            price = item.select_one("div.price")
            if quantity and price:
                price_dict[quantity.text.strip()] = price.text.strip()
    except Exception as e:
        logger.warning(f"Failed to extract price: {e}")
    return price_dict


def get_paginated_reviews(scraper: AliBabaScraper, max_pages: int = 3) -> list[Review]:
    """Get reviews from multiple pages"""
    all_reviews = []
    try:
        # Wait for review section and get pagination
        scraper.driver.wait_for_element("#review-layout", timeout=10)
        pagination = scraper.driver.find_elements(
            "div.detail-pagination-list button:not(.less)"
        )

        if not pagination:
            # Extract reviews from single page
            review_items = BeautifulSoup(
                scraper.driver.page_source, "html.parser"
            ).select("div.review-list > div")
            return [
                extract_review_data(item)
                for item in review_items
                if item.select_one("div.review-intro")
            ]

        # Select random number of pages to scrape
        pages_to_scrape = min(random.randint(2, max_pages), len(pagination))
        logger.debug(f"Scraping {pages_to_scrape} pages of reviews")

        # Process each page
        for page in range(1, pages_to_scrape + 1):
            # Get current page reviews
            review_items = BeautifulSoup(
                scraper.driver.page_source, "html.parser"
            ).select("div.review-list > div")
            if review_items:
                for item in review_items:
                    review = extract_review_data(item)
                    if review["text"]:
                        all_reviews.append(review)
                    else:
                        logger.debug("Skipping empty review")
            else:
                logger.warning("No reviews found on page")

            if page < pages_to_scrape:
                # Click next page with random delay
                time.sleep(random.uniform(0.5, 2))

                # Find the next page button using the pagination structure
                pagination = scraper.driver.find_element(
                    By.CSS_SELECTOR, ".detail-pagination-list"
                )
                active_button = pagination.find_element(
                    By.CSS_SELECTOR, "button.active"
                )
                next_buttons = pagination.find_elements(By.TAG_NAME, "button")

                # Find the button after the active one
                for i, button in enumerate(next_buttons):
                    if button == active_button and i + 1 < len(next_buttons):
                        next_buttons[i + 1].click()
                        time.sleep(random.uniform(0.5, 1.5))
                        break
                else:
                    raise Exception("Could not find next page button")

    except Exception as e:
        logger.error(f"Error during review pagination: {e}")

    return all_reviews


def extract_reviews(soup: BeautifulSoup) -> list[Review]:
    reviews = []
    try:
        review_items = soup.select("div.review-list")
        for review_item in review_items:
            review = extract_review_data(review_item)
            if review["text"]:
                reviews.append(review)
    except Exception as e:
        logger.warning(f"Failed to extract reviews: {e}")
    return reviews


def extract_review_data(review_item: Tag) -> Review:
    # Find review container using select instead of find
    company_review = review_item.select_one("div.company-review")
    review_intro = (
        company_review.select_one("div.review-item div.review-intro")
        if company_review
        else review_item.select_one("div.review-intro")
    )

    review_reply_text = None

    if not review_intro:
        return Review(rating=0.0, text="", translated_text=False, response_text=None)

    # Extract star rating using select
    star_rating = len(review_intro.select("svg.fa-star"))

    # Extract review text
    review_info = review_intro.select_one("div.review-info")
    review_text = review_info.text.strip() if review_info else ""

    # Check if review is translated
    translated_text = False
    review_text = (
        review_text.encode("ascii", "ignore").decode("ascii").replace("\n", " ")
    )

    review_translate = review_intro.select_one("div.review-translate")
    if review_translate:
        translated_text = True

    review_reply = review_item.select_one("div.review-reply")
    if review_reply:
        review_reply_text = review_reply.select_one("div.review-info")
        if review_reply_text:
            review_reply_text = review_reply_text.text.strip()
        else:
            review_reply_text = ""

    return Review(
        rating=float(star_rating),
        text=review_text,
        translated_text=translated_text,
        response_text=review_reply_text if review_reply_text else None,
    )

def get_search_url(query: str) -> str:
    base_url = "https://www.alibaba.com/trade/search"
    params = {
        "spm": "a2700.product_home_newuser.home_new_user_first_screen_fy23_pc_search_bar.searchButton",
        "tab": "all",
        "SearchText": query
    }
    query_string = "&".join([f"{key}={value}" for key, value in params.items()])
    return f"{base_url}?{query_string}"

def get_product_links(search_query: str, scraper) -> list[str]:
    if scraper.get(get_search_url(search_query)):

        data = scraper.driver.page_source
        soup = BeautifulSoup(data, 'html.parser')
        links = soup.find_all('a', href=True)
        return [link['href'] for link in links if 'alibaba.com/product-detail/' in link['href']]
    else:
        logger.error("Failed to load search results")
        return []

def get_product_information(url: str,scraper,first:bool) -> AlibabaProduct:

    if scraper.get(url):
        if first:
            scraper.accept_cookies_ex()
            first = False
        data = scraper.driver.page_source
        time.sleep(random.randint(1, 5))
        soup = BeautifulSoup(data, "html.parser")
        title = extract_title(soup)
        key_attributes = extract_key_attributes(soup)
        lead_time = extract_lead_time(soup)
        price = extract_price(soup)
        reviews = get_paginated_reviews(scraper=scraper, max_pages=20)
        return AlibabaProduct(
            title=title,
            key_attributes=key_attributes,
            price=price,
            reviews=reviews,
            lead_time=lead_time,
        )
    else:
        logger.error("Failed to load page")
        return AlibabaProduct(title="Error", key_attributes={}, price={}, reviews=[], lead_time={})

if __name__ == "__main__":
    with AliBabaScraper(headless=False) as scraper:
        product_list = []
        search_term = "portable air conditioner"
        urls =get_product_links(search_term, scraper)
        for url in urls:
            url = "https:" + url 
            product = get_product_information(url,scraper,first=True)
            time.sleep(random.randint(1, 3))
            product_list.append(product)
            # Convert product list to DataFrame
            data = []
            for product in product_list:
                # Flatten the nested structure
                row = {
                    'title': product.title,
                    'key_attributes': str(product.key_attributes),
                    'price': str(product.price),
                    'lead_time': str(product.lead_time)
                }
                
                # Add reviews as separate columns
                for i, review in enumerate(product.reviews):
                    row[f'review_{i+1}_rating'] = review['rating']
                    row[f'review_{i+1}_text'] = review['text']
                    row[f'review_{i+1}_translated'] = review['translated_text']
                    row[f'review_{i+1}_response'] = review['response_text']

                data.append(row)

            df = pd.DataFrame(data)

            # Save to CSV
            df.to_csv(f'{search_term}_products.csv', index=False, encoding='utf-8')
            print(f"Data saved to {search_term}_products.csv")