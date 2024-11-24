from dataclasses import dataclass
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import pandas as pd


@dataclass
class Product:
    title: str
    price: float | str
    about_product: str | list[str]
    rating: float | str
    reviews: list[dict[str,str | float]]
    
    def __iter__(self):
        yield 'title', self.title
        yield 'price', self.price
        yield 'about_product', self.about_product
        yield 'rating', self.rating
        yield 'reviews', self.reviews

    @classmethod
    def save_product_data(cls, products: list['Product'], filename: str = "amazon_products.csv"):
        data = {
            "product_name": [p.title for p in products],
            "price": [p.price for p in products],
            "about_product": [p.about_product for p in products],
            "reviews": [p.reviews for p in products],
            "rating": [p.rating for p in products]
        }
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        
class Scraper:
    def __init__(self, headless = True,
        load_images = False, # for faster scraping we can turn off image loading
        options = Options(), # options for the web surfer
        window_size = (700,900)):

        if headless:
            # if headless is True, we can run the scraper 
            # without opening a browser
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            
        prefs: dict[str, str | int] = {"intl.accept_languages": "en"}
        if not load_images:
            prefs["profile.managed_default_content_settings.images"] = 2
            options.add_experimental_option("prefs", prefs)
        # adding some more options to the web surfer
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        # creating the websurfer using chrome
        self.driver = webdriver.Chrome(options=options)
        self.driver.set_window_size(*window_size)
