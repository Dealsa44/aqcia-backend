import requests
import time
from datetime import datetime
import csv
import traceback

# --- Constants ---
BASE_URL = "https://sparonline.ge/api/products"
CATEGORIES_URL = "https://sparonline.ge/api/categories"
SUBCATEGORIES_URL = "https://sparonline.ge/api/categories/{category_id}/subcategories"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

CSV_FILE = f"spar_products_{datetime.utcnow().strftime('%Y%m%d')}.csv"

# --- Fetch functions ---
def fetch_categories():
    try:
        resp = requests.get(CATEGORIES_URL, headers=HEADERS)
        resp.raise_for_status()
        return resp.json().get("categories", [])
    except Exception as e:
        print("Error fetching categories:", e)
        return []

def fetch_subcategories(category_id):
    try:
        url = SUBCATEGORIES_URL.format(category_id=category_id)
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        return resp.json().get("subcategories", [])
    except Exception as e:
        print("Error fetching subcategories:", e)
        return []

def fetch_products_from_api(parent_category_id, subcategory_id=None, page_number=1, page_size=50):
    params = {
        "category": parent_category_id,
        "page": page_number,
        "pageSize": page_size
    }
    if subcategory_id:
        params["subcategory"] = subcategory_id
    try:
        response = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching products page {page_number} for category {parent_category_id}: {e}")
        return None

# --- CSV Saving ---
def save_products_to_csv(products):
    if not products:
        print("No products to save.")
        return
    keys = products[0].keys()
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(products)
    print(f"Saved {len(products)} products to {CSV_FILE}")

# --- Parser ---
def parse_and_collect_products(api_data, category, subcategory):
    collected = []
    try:
        grouped_products = api_data.get("products", [])
        for p in grouped_products:
            product = {
                "Product ID": p.get("id"),
                "Name": p.get("name"),
                "Price": p.get("price"),
                "Previous Price": p.get("previousPrice"),
                "Is On Sale": bool(p.get("previousPrice")),
                "Category": category.get("name"),
                "Subcategory": subcategory.get("name") if subcategory else None,
                "Image URL": p.get("imageUrl")
            }
            collected.append(product)
    except Exception as e:
        print("Error parsing products:")
        traceback.print_exc()
    return collected

# --- Main Scraper Logic ---
def run_scrape():
    print(f"[{datetime.now()}] Starting SPAR scrape...")
    all_products = []
    try:
        categories = fetch_categories()
        for cat in categories:
            print(f"Category: {cat.get('name')}")
            subcategories = fetch_subcategories(cat["id"])
            if not subcategories:
                subcategories = [None]  # Handle flat structure
            for subcat in subcategories:
                page = 1
                while True:
                    print(f"Fetching page {page} for category {cat['id']} subcategory {subcat['id'] if subcat else 'N/A'}")
                    data = fetch_products_from_api(cat["id"], subcat["id"] if subcat else None, page_number=page)
                    if not data:
                        break
                    parsed = parse_and_collect_products(data, cat, subcat)
                    if not parsed:
                        break
                    all_products.extend(parsed)
                    if not data.get("hasNextPage"):
                        break
                    page += 1
                    time.sleep(1)
        save_products_to_csv(all_products)
    except Exception as e:
        print("Fatal error in run_scrape:")
        traceback.print_exc()
    print(f"[{datetime.now()}] Scrape complete.")

if __name__ == "__main__":
    run_scrape()
