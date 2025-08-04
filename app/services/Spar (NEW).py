import requests
from bs4 import BeautifulSoup
import csv
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional

BASE_URL = "https://spartonline.ge"
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}
DELAY_BETWEEN_REQUESTS = 1.5
MAX_RETRIES = 3
CSV_FILENAME = f"products_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"


logging.basicConfig(
    filename="scraper.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_soup(url: str, retries: int = MAX_RETRIES) -> Optional[BeautifulSoup]:
    """
    Sends a GET request to the given URL and returns a BeautifulSoup object.
    Retries on failure up to `retries` times.
    """
    for attempt in range(retries):
        try:
            logging.info(f"Fetching URL: {url}")
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            logging.warning(f"Attempt {attempt+1} failed for {url}: {e}")
            time.sleep(DELAY_BETWEEN_REQUESTS)
    logging.error(f"Failed to fetch {url} after {retries} attempts.")
    return None


def fetch_categories() -> List[Dict]:
    """
    Fetches all main product categories from the homepage.
    """
    soup = get_soup(BASE_URL)
    if not soup:
        return []

    categories = []
    # TODO: Adjust selector based on spartonline.ge structure
    for a in soup.select("ul.menu li a"):
        href = a.get("href")
        name = a.get_text(strip=True)
        if href and "/category/" in href:
            categories.append({
                "name": name,
                "url": href if href.startswith("http") else BASE_URL + href
            })
    return categories


def fetch_product_links(category_url: str) -> List[str]:
    """
    Given a category URL, return all product links across paginated pages.
    """
    product_links = []
    page = 1

    while True:
        paged_url = f"{category_url}?page={page}"
        soup = get_soup(paged_url)
        if not soup:
            break

        # TODO: Adjust selector based on spartonline.ge
        links = soup.select("a.product-image")  # Example selector
        if not links:
            logging.info(f"No more products found at page {page}")
            break

        for link in links:
            href = link.get("href")
            if href:
                product_links.append(BASE_URL + href)

        logging.info(f"Found {len(links)} products on page {page}")
        page += 1
        time.sleep(DELAY_BETWEEN_REQUESTS)

    return product_links


def parse_product_details(url: str) -> Optional[Dict]:
    """
    Extracts relevant product data from a product detail page.
    """
    soup = get_soup(url)
    if not soup:
        return None

    try:
        # TODO: Adjust selectors
        name = soup.select_one("h1.product-title").text.strip()
        price = soup.select_one(".product-price .current").text.strip().replace("₾", "").replace(",", ".")
        old_price_tag = soup.select_one(".product-price .old")
        sale_price = old_price_tag.text.strip().replace("₾", "").replace(",", ".") if old_price_tag else ''
        image_tag = soup.select_one(".product-image img")
        image_url = image_tag.get("src") if image_tag else ''

        return {
            "Product Name": name,
            "Price (GEL)": price,
            "Sale Price (GEL)": sale_price,
            "Image URL": image_url,
            "Product URL": url
        }

    except Exception as e:
        logging.error(f"Error parsing product at {url}: {e}")
        return None


def write_to_csv(products: List[Dict], filename: str = CSV_FILENAME):
    """
    Saves a list of product dictionaries into a CSV file.
    """
    if not products:
        logging.warning("No product data to write.")
        return

    with open(filename, mode="w", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=products[0].keys())
        writer.writeheader()
        for product in products:
            writer.writerow(product)

    logging.info(f"Saved {len(products)} products to {filename}")


def scrape_site():
    """
    Main scraper function.
    """
    all_products = []
    categories = fetch_categories()
    logging.info(f"Found {len(categories)} categories.")

    for cat in categories:
        logging.info(f"Scraping category: {cat['name']}")
        product_links = fetch_product_links(cat["url"])
        logging.info(f"Found {len(product_links)} product links in {cat['name']}")

        for idx, url in enumerate(product_links):
            logging.info(f"Processing ({idx+1}/{len(product_links)}): {url}")
            product = parse_product_details(url)
            if product:
                product["Category"] = cat["name"]
                all_products.append(product)
            time.sleep(1)

    write_to_csv(all_products)


if __name__ == "__main__":
    try:
        start = time.time()
        print("Starting SPAR Online scraper...")
        scrape_site()
        print(f"Done. CSV file saved: {CSV_FILENAME}")
        print(f"Total time: {round(time.time() - start, 2)}s")
    except KeyboardInterrupt:
        print("Scraper interrupted by user.")
    except Exception as e:
        logging.critical(f"Fatal error: {e}")
        print("A fatal error occurred. Check scraper.log.")

