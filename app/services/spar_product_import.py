import requests
from bs4 import BeautifulSoup
from datetime import datetime
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Product, Price, Store, Category

BASE_URL = "https://sparonline.ge"

CATEGORY_KEYWORDS = {
    "Milk & Dairy": ["milk", "cheese", "yogurt", "butter", "egg"],
    "Meat & Fish": ["meat", "fish", "chicken", "beef", "sausage"],
    "Drinks": ["juice", "cola", "soda", "water", "tea", "coffee"],
    "Snacks": ["chips", "snack", "chocolate", "cookie", "biscuit"],
    "Bakery": ["bread", "bakery", "pastry", "cake"],
    "Frozen": ["frozen", "ice", "ice‑cream"],
    "Sweets": ["sweet", "candy", "chocolate"],
    "Coffee & Tea": ["coffee", "tea", "cocoa"],
    "Household & Hygiene": ["soap", "detergent", "cleaner", "hygiene", "tissue"],
    "Animal Care": ["pet", "animal", "dog", "cat", "food"],
    "Other": []
}

def categorize_product(name):
    name_lower = name.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(k in name_lower for k in keywords):
            return category
    return "Other"

def fetch_and_store_products():
    db: Session = SessionLocal()

    spar_store = db.query(Store).filter(Store.name == "Spar").first()
    if not spar_store:
        print("❌ 'Spar' store not found in database.")
        return

    page = 1
    while True:
        url = f"{BASE_URL}/en/catalog?page={page}"
        print(f"Fetching: {url}")
        resp = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
        if resp.status_code != 200:
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        products = soup.select("div.catalog-item") or soup.select("div.product-item")
        if not products:
            break

        for p in products:
            name_elem = p.select_one(".title") or p.select_one(".product-name")
            price_elem = p.select_one(".price") or p.select_one(".product-price")
            img = p.select_one("img")
            if not name_elem:
                continue

            name = name_elem.text.strip()
            raw_price = price_elem.text.strip() if price_elem else "0"
            try:
                price = float(raw_price.replace("₾", "").replace(",", ".").strip())
            except ValueError:
                price = 0.0

            image = img['src'] if img and img.has_attr("src") else None
            category_name = categorize_product(name)

            category = db.query(Category).filter_by(name=category_name).first()
            if not category:
                category = Category(name=category_name)
                db.add(category)
                db.commit()
                db.refresh(category)

            product = db.query(Product).filter_by(name=name, store_id=spar_store.store_id).first()
            if not product:
                product = Product(name=name, image=image, store_id=spar_store.store_id, category_id=category.category_id)
                db.add(product)
                db.commit()
                db.refresh(product)

            new_price = Price(product_id=product.product_id, price=price, date=datetime.utcnow())
            db.add(new_price)

        db.commit()
        page += 1

    print("✅ Finished fetching and storing products.")
