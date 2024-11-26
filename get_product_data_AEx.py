from bs4 import BeautifulSoup
from information_types import Product, Scraper
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

BASE_URL: str = "https://www.aliexpress.com/w/wholesale-"
URL_SUFFIX: str = ".html"

def get_product_page_data_AE(scraper: Scraper, url: str, max_reviews: int = 50) -> Product:
    # Wait for the page to load
    scraper.driver.get(url)
    time.sleep(3)  
    soup = BeautifulSoup(scraper.driver.page_source, "html.parser")
    # Extract specifications
    spec_list = []
    reviews = []
    
    
    specifications = soup.select("div.specification--prop--Jh28bKu")
    for spec in specifications:
        title_element = spec.select_one("div.specification--title--SfH3sA8")
        desc_element = spec.select_one("div.specification--desc--Dxx6W0W")
        if title_element and desc_element:
            title = title_element.get_text(strip=True)
            description = desc_element.get_text(strip=True)
            spec_list.append(f"{title}: {description}")

    # Extract title and price
    title_elem = soup.select_one("h1[data-pl='product-title']")
    title = title_elem.get_text(strip=True) if title_elem else "N/A"
    price_elem = soup.select_one("span.price--currentPriceText--V8_y_b5.pdp-comp-price-current.product-price-value")
    price = price_elem.get_text(strip=True) if price_elem else "N/A"
    # Extract star rating from the rating element 
    stars_element = soup.select_one("div.header--num--GaAGwoZ")
    stars = float(stars_element.get_text(strip=True)) if stars_element else 0
    # Click "View More" to load reviews
    try:
        # Try CSS selector first
        show_more_button = WebDriverWait(scraper.driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 
                "button.comet-v2-btn.comet-v2-btn-slim.comet-v2-btn-large.comet-v2-btn-important"))
        )
        
        # If CSS fails, try XPath as backup
        if not show_more_button:
            show_more_button = WebDriverWait(scraper.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, 
                    "//button[contains(@class, 'comet-v2-btn-important')]//font[contains(text(), 'Show More')]"))
            )
        
        # Scroll button into view
        scraper.driver.execute_script("arguments[0].scrollIntoView(true);", show_more_button)
        time.sleep(1)
        
        # Click using JavaScript
        scraper.driver.execute_script("arguments[0].click();", show_more_button)
        time.sleep(2)

    except Exception as e:
        print(f"Failed to click 'Show More' button: {e}")
    # Optional: Take screenshot for debugging
    scraper.driver.save_screenshot("error_screenshot.png")
    # Load reviews

    try:
        reviews_container = scraper.driver.find_element(By.CLASS_NAME, "comet-v2-modal-body")
        scraper.driver.execute_script("arguments[0].scrollIntoView(true);", reviews_container)
        while len(reviews) < max_reviews:
            scraper.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", reviews_container)
            time.sleep(1)
            soup = BeautifulSoup(scraper.driver.page_source, "html.parser")
            review_elements = soup.select("div.list--itemWrap--ARYTMbR")
            for element in review_elements:
                if len(reviews) >= max_reviews:
                    break
                rating = len(element.select("span.comet-icon-starreviewfilled"))
                review_text_elem = element.select_one("div.list--itemReview--xQUhO78")
                review_text = review_text_elem.get_text(strip=True) if review_text_elem else ""
                review_text = review_text.encode('ascii', 'ignore').decode('ascii').replace("\n", " ")
                reviews.append({"content": review_text, "rating": rating})
            if not review_elements:
                break
    except Exception as e:
        print(f"Failed to load reviews: {e}")

    # Parse reviews
    soup = BeautifulSoup(scraper.driver.page_source, "html.parser")
    review_elements = soup.select("div.list--itemWrap--ARYTMbR")[:max_reviews]
    for element in review_elements:
        rating = len(element.select("span.comet-icon-starreviewfilled"))
        review_text_elem = element.select_one("div.list--itemReview--xQUhO78")
        review_text = review_text_elem.get_text(strip=True) if review_text_elem else ""
        # clean text from emojis and \n 
        review_text = review_text.encode('ascii', 'ignore').decode('ascii').replace("\n", " ")
        reviews.append({"content": review_text, "rating": rating})

    return Product(title=title, price=price,rating=stars if stars else 0, about_product=spec_list, reviews=reviews)

def get_product_urls_AE(scraper: Scraper, search_query: str, max_page_number: int = 4) -> list[str]:
    formatted_query = search_query.replace(" ", "-")
    initial_url = f"{BASE_URL}{formatted_query}{URL_SUFFIX}"
    scraper.driver.get(initial_url)
    product_urls = []
    current_page = 1
    
    try:
        # Try to find cookie button
        cookie_button = WebDriverWait(scraper.driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "btn-accept"))
        )
        
        # Scroll button into view
        scraper.driver.execute_script("arguments[0].scrollIntoView(true);", cookie_button)
        time.sleep(1)
        
        # Try JavaScript click
        scraper.driver.execute_script("arguments[0].click();", cookie_button)
        
        # Wait for cookie banner to disappear
        WebDriverWait(scraper.driver, 10).until(
            EC.invisibility_of_element_located((By.CLASS_NAME, "global-gdpr-container-y2023"))
        )
        
    except Exception as e:
        print(f"Error handling cookie consent: {e}")
        # Try alternative method with direct JavaScript
        try:
            scraper.driver.execute_script("""
                document.querySelector('.btn-accept').click();
            """)
            time.sleep(2)
        except Exception as e2:
            print(f"Alternative cookie handling failed: {e2}")
    while current_page <= max_page_number:
        # Scroll down gradually to trigger lazy loading
        last_height = scraper.driver.execute_script("return document.body.scrollHeight")
        while True:
            # Scroll down in smaller increments
            for i in range(0, last_height, 500):
                scraper.driver.execute_script(f"window.scrollTo(0, {i});")
                time.sleep(1)  # Short pause to let content load

            # Calculate new scroll height and check if we've reached the bottom
            new_height = scraper.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # Wait for elements to be present
        WebDriverWait(scraper.driver, 5).until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, ".list--gallery--C2f2tvm.search-item-card-wrapper-gallery")
            )
        )

        soup = BeautifulSoup(scraper.driver.page_source, "html.parser")
        search_results = soup.find_all('div', {'class': 'list--gallery--C2f2tvm search-item-card-wrapper-gallery'})
        
        for result in search_results:
            product_link = result.find("a", {"class": "multi--container--1UZxxHY cards--card--3PJxwBm search-card-item"})
            if product_link and (link := product_link.get("href")):
                link_url = "http:" + link
                if link_url.startswith("http://nl."):
                    link_url = link_url.replace("http://nl.", "http://", 1)
                product_urls.append(link_url)

        current_page += 1
        if current_page <= max_page_number:
            next_url = f"{initial_url}?page={current_page}"
            scraper.driver.get(next_url)
        else:
            break

    return product_urls

if __name__ == "__main__":
    search_query = "wireless earbuds"
    scraper = Scraper(headless=False, load_images=True)
    product_urls = get_product_urls_AE(scraper, search_query,1)
    products = []
    for url in product_urls:
        product = get_product_page_data_AE(scraper, url)
        products.append(product)
        print(product)
    scraper.driver.quit()
    Product.save_product_data(products, "aliexpress_products.csv")
    