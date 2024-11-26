"""
Amazon Product Scraper
---------------------

A web scraping module for extracting product information from Amazon Netherlands (amazon.nl).
Uses Selenium WebDriver and BeautifulSoup for automated data collection.

Constants:
    BASE_URL (str): Base search URL for Amazon Netherlands

Classes:
    Product: Dataclass for storing product information
        Attributes:
            title (str): Product name
            price (float|str): Product price 
            about_product (str|list): Product description/features
            rating (float|str): Product rating
            reviews (list[dict]): List of product reviews
        
        Methods:
            __iter__: Makes class iterable for easy dict conversion
            save_product_data: Static method to save products to CSV

    Scraper: Configures and manages Chrome WebDriver
        Args:
            headless (bool): Run browser without GUI (default: True)
            load_images (bool): Load page images (default: False)
            options (Options): Chrome WebDriver options
            window_size (tuple): Browser window size (default: 700x900)

Functions:
    get_product_urls_az:
        Gets product URLs from Amazon search results
        Args:
            scraper (Scraper): Scraper instance
            search_query (str): Search term
            max_page_number (int): Pages to scrape (default: 4) 
            skip_ads (bool): Skip sponsored products (default: True)
            results_in_dutch (bool): Get Dutch results (default: False)
        Returns:
            list[str]: List of product URLs

    get_product_data_az:
        Scrapes detailed product information
        Args:
            scraper (Scraper): Scraper instance
            url (str): Product page URL
        Returns:
            Product: Product object with scraped data

Main workflow:
1. Initialize Scraper
2. Get product URLs from search
3. Scrape details for each product
4. Save results to CSV

Example usage:
    scraper = Scraper()
    urls = get_product_urls_az(scraper, "laptop", max_page_number=1)
    products = [get_product_data_az(scraper, url) for url in urls]
    Product.save_product_data(products)
"""

from bs4 import BeautifulSoup, Tag
from urllib.parse import quote
from information_types import Product, Scraper
BASE_URL: str = "https://www.amazon.nl/s?k="


def get_product_urls_az(
    scraper: Scraper,
    search_query: str,
    max_page_number: int = 4,
    skip_ads: bool = True,
    results_in_dutch: bool = False,
) -> list[str]:
    formatted_query = quote(search_query)
    if results_in_dutch:
        initial_url = f"{BASE_URL}{formatted_query}"
    else:
        initial_url = f"{BASE_URL}{formatted_query}&language=en_GB"
    scraper.driver.get(initial_url)
    product_urls = []
    current_page = 1
    # Loop through search result pages
    while current_page <= max_page_number:
        soup = BeautifulSoup(scraper.driver.page_source, "html.parser")
        search_results = soup.find_all(
            "div", {"data-component-type": "s-search-result"}
        )
    # Extract product URLs from search results
        for result in search_results:
            if skip_ads and result.find("span", {"class": "puis-label-popover-hover"}):
                continue
            product_link = result.find("a", {"class": "a-link-normal s-no-outline"})
            if product_link:
                href = product_link.get("href")
                if href:
                    product_urls.append(href)
    # Navigate to next page
        current_page += 1
        if current_page <= max_page_number:
            next_url = f"{initial_url}&page={current_page}"
            scraper.driver.get(next_url)

    return product_urls

def get_product_data_az(scraper: Scraper, url: str) -> Product:
    # Initialize default values
    title = "Title not found"
    price = "Price not found"
    rating = 0.0
    about_product = []
    reviews_list = []
    # Load product page
    scraper.driver.get(f"https://www.amazon.nl{url}")
    page_data = BeautifulSoup(scraper.driver.page_source, 'html.parser')

    # Get product title
    product_name_element = page_data.find("span", {"id": "productTitle"})
    if product_name_element and product_name_element.text:
        title = product_name_element.text.strip()

    # Get price information
    try:
        price_element = page_data.find("span", {"class": "a-price-whole"})
        price_decimal_element = page_data.find("span", {"class": "a-price-fraction"})
        if price_element and price_decimal_element and price_element.text and price_decimal_element.text:
            price = float(price_element.text.replace(',', '') + price_decimal_element.text)
    except (ValueError, AttributeError):
        pass

    # Get product description
    labels_element = page_data.find("ul", {"class": "a-unordered-list a-vertical a-spacing-mini"})
    if labels_element and hasattr(labels_element, 'find_all'):
        if isinstance(labels_element,Tag):        
            list_items = labels_element.find_all("li", {"class": "a-spacing-mini"})
            for item in list_items:
                label = item.find("span", {"class": "a-list-item"})
                if label and label.text:
                    
                    about_product.append(label.text.strip())
                else:
                    print("No label found")
                    about_product.append(item.text.strip())
        else:
            print("No labels found")
            about_product.append(labels_element.text.strip())
            
    # Get rating

    rating_element = page_data.select_one("#acrPopover")
    if rating_element:
        text_rating = rating_element.get("title")
        if isinstance(text_rating, str):
            rating = float(text_rating.split()[0].replace(",", "."))
        else:
            rating = float(rating_element.text.split()[0].replace(",", "."))

    # Get reviews
    reviews = page_data.find_all("div", {"data-hook": "review"})
    reviews_list = []
    for review in reviews:
        review_title_element = review.find("a", {"data-hook": "review-title"})
        review_title = review_title_element.text.strip().split('\n', 1)[-1] if review_title_element else "Title not found"

        review_text_element = review.find("span", {"data-hook": "review-body"})
        if not review_text_element:
            review_text_element = review.find("span", {"class": "cr-original-review-content"})
        review_text = review_text_element.text.strip().replace('Read more', '').strip() if review_text_element else "Review text not found"

        review_rating_element = review.find("i", {"data-hook": "review-star-rating"}) or review.find("span", {"class": "a-icon-alt"})
        review_rating = float(review_rating_element.text.split()[0].replace(',', '.')) if review_rating_element else 0.0

        reviews_list.append({
            "title": review_title,
            "text": review_text,
            "rating": review_rating
        })
    return Product(
        title=title,
        price=price,
        rating=rating,
        about_product="\n".join(about_product),
        reviews=reviews_list
    )

if __name__ == "__main__":
    scraper = Scraper()
    product_urls = get_product_urls_az(scraper, "laptop", max_page_number=1)
    products = []
    for url in product_urls:
        product = get_product_data_az(scraper, url)
        products.append(product)
    Product.save_product_data(products)
        
