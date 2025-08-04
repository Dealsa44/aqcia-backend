import sys
import os
import time
from datetime import datetime, timedelta
import subprocess
import schedule

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import Product, Price, Store, Category


def verify_data():
    db: Session = SessionLocal()
    print("\n--- Verifying Scraper Data ---\n")

    try:
        print("\n[1] Checking for 'Spar' store...")
        spar_store = db.query(Store).filter(Store.name == "Spar").first()
        if spar_store:
            print(f"✅ SUCCESS: Found store '{spar_store.name}' (ID: {spar_store.store_id}).")
        else:
            print("❌ FAILED: 'Spar' store not found.")
            return

        print("\n[2] Checking for recently added products...")
        recent_products = db.query(Product).order_by(Product.product_id.desc()).limit(5).all()
        if recent_products:
            print(f"✅ SUCCESS: Found {len(recent_products)} recent products.")
            for p in recent_products:
                print(f" - Product: {p.name} | Unit: {p.unit if hasattr(p, 'unit') else 'N/A'} (ID: {p.product_id})")
        else:
            print("❌ FAILED: No products found in the database.")
            return

        print("\n[3] Checking for recent price entries from Spar...")
        ten_minutes_ago = datetime.utcnow() - timedelta(minutes=10)
        recent_prices = db.query(Price).filter(
            Price.store_id == spar_store.store_id,
            Price.updated_at >= ten_minutes_ago
        ).limit(5).all()

        if recent_prices:
            print(f"✅ SUCCESS: Found {len(recent_prices)} new price entries linked to Spar.")
            for price in recent_prices:
                product = db.query(Product).filter(Product.product_id == price.product_id).first()
                print(f" - Product: {product.name} | Unit: {product.unit if hasattr(product, 'unit') else 'N/A'} | New price: {price.price}")
        else:
            print("ℹ️ INFO: No new prices recorded for Spar in the last 10 minutes.")

        print("\n[4] Checking for categories...")
        categories = db.query(Category).limit(10).all()
        if categories:
            print(f"✅ SUCCESS: Found {len(categories)} categories.")
            for c in categories:
                print(f" - Category: {c.name_en} (ID: {c.id})")
        else:
            print("❌ FAILED: No categories found.")

        print("\n[5] Listing all products in the database...")
        all_products = db.query(Product).all()
        if all_products:
            print(f"✅ SUCCESS: Found {len(all_products)} total products.")
            for product in all_products:
                print(f" - Product: {product.name} | Unit: {product.unit if hasattr(product, 'unit') else 'N/A'} (ID: {product.product_id})")
        else:
            print("❌ FAILED: No products found at all.")

    except Exception as e:
        print(f"❌ ERROR occurred during verification: {e}")
    finally:
        db.close()
        print("\n--- Verification Complete ---\n")


schedule.every(24).hours.do(verify_data)

print("📅 Scheduler started. Running verify_data() every 24 hours...")

verify_data()

while True:
    schedule.run_pending()
    time.sleep(60)
