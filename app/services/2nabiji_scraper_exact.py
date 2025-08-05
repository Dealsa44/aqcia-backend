
import requests
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Product, Price, Store, Category, Subcategory
import traceback
from bs4 import BeautifulSoup

BASE_URL = "https://2nabiji.ge/ge"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def fetch_categories():
    try:
        response = requests.get(BASE_URL, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        categories = soup.select("ul.menu__list li.menu__item > a")
        return [a['href'] for a in categories if a.get('href')]
    except Exception as e:
        print("Failed to fetch categories:", e)
        return []

def fetch_products(category_url):
    try:
        url = "https://2nabiji.ge" + category_url
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        return soup.select("div.products-list__item")
    except Exception as e:
        print(f"Failed to fetch products from {category_url}:", e)
        return []

def main():
    db: Session = SessionLocal()
    try:
        store = db.query(Store).filter_by(name="2nabiji").first()
        if not store:
            store = Store(name="2nabiji")
            db.add(store)
            db.commit()
            db.refresh(store)

        categories = fetch_categories()
        for cat_url in categories:
            try:
                category_name = cat_url.strip("/").split("/")[-1]
                category = db.query(Category).filter_by(name=category_name, store_id=store.id).first()
                if not category:
                    category = Category(name=category_name, store_id=store.id)
                    db.add(category)
                    db.commit()
                    db.refresh(category)

                products = fetch_products(cat_url)
                for product in products:
                    try:
                        name = product.select_one(".product__title").get_text(strip=True)
                        price_text = product.select_one(".product__price--current").get_text(strip=True).replace("₾", "").replace(",", ".")
                        try:
                            price = Decimal(price_text)
                        except InvalidOperation:
                            print(f"Invalid price for {name}")
                            continue

                        product_url = "https://2nabiji.ge" + product.select_one("a")["href"]
                        image_tag = product.select_one(".product__img img")
                        image_url = image_tag["src"] if image_tag else None

                        existing_product = db.query(Product).filter_by(name=name, store_id=store.id).first()
                        if not existing_product:
                            new_product = Product(
                                name=name,
                                store_id=store.id,
                                category_id=category.id,
                                subcategory_id=None,
                                url=product_url,
                                image=image_url
                            )
                            db.add(new_product)
                            db.commit()
                            db.refresh(new_product)
                            product_id = new_product.id
                        else:
                            product_id = existing_product.id

                        new_price = Price(
                            product_id=product_id,
                            price=price,
                            date=datetime.utcnow()
                        )
                        db.add(new_price)
                        db.commit()

                    except Exception as e:
                        print("Error processing product:", e)
                        traceback.print_exc()
                time.sleep(1)
            except Exception as e:
                print("Error processing category:", e)
                traceback.print_exc()
    except Exception as e:
        print("Fatal error:", e)
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
