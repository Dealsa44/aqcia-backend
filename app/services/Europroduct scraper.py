import requests
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Product, Price, Store, Category, Subcategory
import traceback

GRAPHQL_URL = "https://api.europroduct.ge/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0"
}

def get_categories():
    query = {
        "query": "{ categories { id name } }"
    }
    response = requests.post(GRAPHQL_URL, json=query, headers=HEADERS)
    response.raise_for_status()
    data = response.json()
    return data["data"]["categories"]

def get_products_by_category(category_id):
    graphql_query = """
    query getCategoryProducts($id: Int!) {
        category(id: $id) {
            products {
                id
                name
                price
                image
            }
        }
    }
    """
    variables = {"id": category_id}
    payload = {"query": graphql_query, "variables": variables}
    response = requests.post(GRAPHQL_URL, json=payload, headers=HEADERS)
    response.raise_for_status()
    data = response.json()
    return data["data"]["category"]["products"]

def main():
    db: Session = SessionLocal()
    try:
        store = db.query(Store).filter_by(name="Europroduct").first()
        if not store:
            store = Store(name="Europroduct")
            db.add(store)
            db.commit()
            db.refresh(store)

        categories = get_categories()
        for cat in categories:
            try:
                category_name = cat["name"]
                category_id = cat["id"]

                category = db.query(Category).filter_by(name=category_name, store_id=store.id).first()
                if not category:
                    category = Category(name=category_name, store_id=store.id)
                    db.add(category)
                    db.commit()
                    db.refresh(category)

                products = get_products_by_category(category_id)
                for prod in products:
                    try:
                        name = prod["name"]
                        price_text = str(prod["price"]).replace(",", ".")
                        try:
                            price = Decimal(price_text)
                        except InvalidOperation:
                            print(f"Invalid price for {name}")
                            continue

                        product_url = f"https://europroduct.ge/product/{prod['id']}"
                        image_url = prod["image"]

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

