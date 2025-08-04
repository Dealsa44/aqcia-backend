import requests
import csv
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional

BASE_API_TEMPLATE = "https://spartonline.ge/api/products?page={page}&category={category_id}"
CATEGORY_ID = 34  # TODO: Replace with actual category ID from DevTools
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}
MAX_RETRIES = 3
REQUEST_DELAY = 1.5
LOG_FILE = "spar_scraper.log"
CSV_FILENAME = f"spar_products_{CATEGORY_ID}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

=logging.basicConfig(
    filename=LOG_FILE,
    filemode='a',
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def get_json(url: str, retries: int = MAX_RETRIES) -> Optional[dict]:
    """
    Makes a GET request to the provided URL and returns JSON.
    Retries on failure.
    """
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.warning(f"[Attempt {attempt}] Failed to fetch {url}: {e}")
            time.sleep(REQUEST_DELAY)
    logging.error(f"Failed after {retries} attempts: {url}")
    return None

def parse_product(product: dict) -> Optional[Dict[str, str]]:
    """
    Extracts and returns relevant fields from a single product JSON object.
    """
    try:
        return {
            "ID": str(product.get("id")),
            "Name": product.get("name", "").strip(),
            "Price (GEL)": str(product.get("price")),
            "Previous Price (GEL)": str(product.get("previousPrice") or ""),
            "Is On Sale": str(bool(product.get("previousPrice"))),
            "Image URL": product.get("imageUrl", ""),
            "Barcode": product.get("barCode", ""),
        }
    except Exception as e:
        logging.error(f"Error parsing product: {e}")
        return None

def fetch_all_products(category_id: int) -> List[Dict[str, str]]:
    """
    Loops through paginated product listings for a given category.
    Returns a list of parsed product dictionaries.
    """
    page = 1
    all_products = []

    while True:
        url = BASE_API_TEMPLATE.format(page=page, category_id=category_id)
        logging.info(f"Fetching page {page} → {url}")
        print(f"Fetching page {page}...")

        json_data = get_json(url)
        if not json_data:
            break

        items = json_data.get("products", [])
        if not items:
            logging.info("No products found on this page.")
            break

        for item in items:
            parsed = parse_product(item)
            if parsed:
                all_products.append(parsed)

        # Check pagination structure
        has_next = json_data.get("hasNextPage") \
                    or json_data.get("pagination", {}).get("hasNext") \
                    or json_data.get("hasNext", False)

        if not has_next:
            logging.info("No more pages left.")
            break

        page += 1
        time.sleep(REQUEST_DELAY)

    return all_products

def save_to_csv(data: List[Dict[str, str]], filename: str = CSV_FILENAME):
    """
    Writes parsed product data to a CSV file.
    """
    if not data:
        logging.warning("No data to write.")
        print("[!] No products to write to CSV.")
        return

    try:
        with open(filename, mode="w", newline='', encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            for row in data:
                writer.writerow(row)

        print(f"[✓] CSV saved: {filename} ({len(data)} products)")
        logging.info(f"Saved {len(data)} products to {filename}")
    except Exception as e:
        logging.critical(f"Error writing to CSV: {e}")
        print(f"[!] Error writing CSV: {e}")

def main():
    print(f"🛒 Starting scrape for SPAR category {CATEGORY_ID}")
    logging.info(f"Script started for category ID {CATEGORY_ID}")

    start_time = time.time()

    try:
        products = fetch_all_products(CATEGORY_ID)
        save_to_csv(products)
    except Exception as e:
        logging.exception(f"Fatal error during scraping: {e}")
        print(f"[!] A fatal error occurred: {e}")

    duration = round(time.time() - start_time, 2)
    print(f"🏁 Done in {duration} seconds.")
    logging.info(f"Script completed in {duration}s")

if __name__ == "__main__":
    main()

