import sys
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models import (
    Product, Price, Store, Category, Subcategory,
    Inventory, SmartMatching, PriceHistory, ShoppingListItem,
    Favorite, SaleAlert, Notification
)

def clear_all_data():
    db: Session = SessionLocal()
    try:
        print("Deleting all dependent tables...")
        db.query(Price).delete()
        db.query(Inventory).delete()
        db.query(SmartMatching).delete()
        db.query(PriceHistory).delete()
        db.query(ShoppingListItem).delete()
        db.query(Favorite).delete()
        db.query(SaleAlert).delete()
        db.query(Notification).delete()
        db.commit()
        print("Deleting all products...")
        db.query(Product).delete()
        db.commit()
        print("Deleting all subcategories...")
        db.query(Subcategory).delete()
        db.commit()
        print("Deleting all categories...")
        db.query(Category).delete()
        db.commit()
        print("All data cleared from dependent tables, Product, Subcategory, and Category tables.")
    except Exception as e:
        print(f"Error clearing data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":

    clear_all_data() 
    