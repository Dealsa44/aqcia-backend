
import sys
import os
import time
from datetime import datetime, timedelta
import subprocess
import schedule


sys.path.append(os.path.dirname(os.path.abspath(__file__)))


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
                print(f" - Product: {p.name} (ID: {p.product_id})")
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
                product_name = db.query(Product.name).filter(Product.product_id == price.product_id).scalar()
                print(f" - Product '{product_name}' has new price: {price.price}")
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
                print(f" - Product: {product.name} (ID: {product.product_id})")
        else:
            print("❌ FAILED: No products found at all.")

    except Exception as e:
        print(f"❌ ERROR occurred during verification: {e}")
    finally:
        db.close()
        print("\n--- Verification Complete ---\n")


schedule.every(24).hours.do(verify_data)

# --- START BACKGROUND LOGGING PROCESS ---

def launch_in_background():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(project_dir, __file__)
    log_path = os.path.join(project_dir, "verifier_log.txt")
    command = f"nohup python3 {script_path} >> {log_path} 2>&1 &"
    try:
        subprocess.Popen(command, shell=True)
        print(f"✅ Verifier script launched in background.\nLogging to: {log_path}")
    except Exception as e:
        print(f"❌ Failed to launch script in background: {e}")


if __name__ == "__main__":
    print("🔁 Starting daily verification loop (every 24h)...")
    verify_data()  # Run once now

    while True:
        schedule.run_pending()
        time.sleep(60)
