from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
import logging
import time
 
# Your routers (unchanged)
from app.api.endpoints import (
    products, prices, inventory, users, shopping_lists, favorites,
    sale_alerts, notifications, search, data_collection_router, catalog_router
)
 
from sqladmin import Admin, ModelView
from app.db import models
from app.db.session import engine  # engine uses env DATABASE_URL with sslmode=require
 
app = FastAPI(title="Price Comparison API")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log incoming request
    logger.info(f"🌐 Incoming request: {request.method} {request.url}")
    logger.info(f"📍 Client IP: {request.client.host if request.client else 'unknown'}")
    logger.info(f"🔗 Headers: {dict(request.headers)}")
    
    # Process request
    response = await call_next(request)
    
    # Log response
    process_time = time.time() - start_time
    logger.info(f"✅ Response: {response.status_code} - {process_time:.3f}s")
    
    return response
 
# CORS configuration for frontend domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ashy-stone-06e190203.2.azurestaticapps.net",
        "http://localhost:4200",  # for local development
        "https://localhost:4200"  # for local development with HTTPS
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
 
# Routers
app.include_router(products.router,         prefix="/products",         tags=["Products"])
app.include_router(prices.router,           prefix="/prices",           tags=["Prices"])
app.include_router(inventory.router,        prefix="/inventory",        tags=["Inventory"])
app.include_router(users.router,            prefix="/users",            tags=["Users"])
app.include_router(shopping_lists.router,   prefix="/shopping-lists",   tags=["Shopping Lists"])
app.include_router(favorites.router,        prefix="/favorites",        tags=["Favorites"])
app.include_router(sale_alerts.router,      prefix="/sale-alerts",      tags=["Sale Alerts"])
app.include_router(notifications.router,    prefix="/notifications",    tags=["Notifications"])
app.include_router(search.router,           prefix="/search",           tags=["Search"])
app.include_router(data_collection_router,  prefix="/data-collection",  tags=["Data Collection"])
app.include_router(catalog_router,          prefix="/catalog",          tags=["Categories & Subcategories"])
 
# --- SQLAdmin views (unchanged) ---
class UserAdmin(ModelView, model=models.User):
    column_list = [c.name for c in models.User.__table__.columns]
class SessionAdmin(ModelView, model=models.Session):
    column_list = [c.name for c in models.Session.__table__.columns]
class PreferenceAdmin(ModelView, model=models.Preference):
    column_list = [c.name for c in models.Preference.__table__.columns]
class SearchHistoryAdmin(ModelView, model=models.SearchHistory):
    column_list = [c.name for c in models.SearchHistory.__table__.columns]
class ProductAdmin(ModelView, model=models.Product):
    column_list = [c.name for c in models.Product.__table__.columns]
class SmartMatchingAdmin(ModelView, model=models.SmartMatching):
    column_list = [c.name for c in models.SmartMatching.__table__.columns]
class StoreAdmin(ModelView, model=models.Store):
    column_list = [c.name for c in models.Store.__table__.columns]
class InventoryAdmin(ModelView, model=models.Inventory):
    column_list = [c.name for c in models.Inventory.__table__.columns]
class PriceAdmin(ModelView, model=models.Price):
    column_list = [c.name for c in models.Price.__table__.columns]
class PriceHistoryAdmin(ModelView, model=models.PriceHistory):
    column_list = [c.name for c in models.PriceHistory.__table__.columns]
class ShoppingListAdmin(ModelView, model=models.ShoppingList):
    column_list = [c.name for c in models.ShoppingList.__table__.columns]
class ShoppingListItemAdmin(ModelView, model=models.ShoppingListItem):
    column_list = [c.name for c in models.ShoppingListItem.__table__.columns]
class FavoriteAdmin(ModelView, model=models.Favorite):
    column_list = [c.name for c in models.Favorite.__table__.columns]
class SaleAlertAdmin(ModelView, model=models.SaleAlert):
    column_list = [c.name for c in models.SaleAlert.__table__.columns]
class NotificationAdmin(ModelView, model=models.Notification):
    column_list = [c.name for c in models.Notification.__table__.columns]
 
admin = Admin(app, engine)
admin.add_view(UserAdmin)
admin.add_view(SessionAdmin)
admin.add_view(PreferenceAdmin)
admin.add_view(SearchHistoryAdmin)
admin.add_view(ProductAdmin)
admin.add_view(SmartMatchingAdmin)
admin.add_view(StoreAdmin)
admin.add_view(InventoryAdmin)
admin.add_view(PriceAdmin)
admin.add_view(PriceHistoryAdmin)
admin.add_view(ShoppingListAdmin)
admin.add_view(ShoppingListItemAdmin)
admin.add_view(FavoriteAdmin)
admin.add_view(SaleAlertAdmin)
admin.add_view(NotificationAdmin)
# --- end SQLAdmin ---
 
@app.get("/", tags=["Root"])
def read_root():
    logger.info("🏠 Root endpoint accessed")
    return {"message": "Price Comparison API is running!"}
 
@app.get("/health", tags=["Health"])
def health():
    logger.info("🏥 Health check endpoint accessed")
    try:
        # simple DB liveness check
        from app.db.session import engine as db_engine
        with db_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Health check passed - database connected")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error(f"❌ Health check failed - database error: {str(e)}")
        return {"status": "error", "database": "disconnected", "error": str(e)}

@app.get("/debug", tags=["Debug"])
def debug_info():
    logger.info("🔍 Debug endpoint accessed")
    return {
        "cors_origins": [
            "https://ashy-stone-06e190203.2.azurestaticapps.net",
            "http://localhost:4200",
            "https://localhost:4200"
        ],
        "app_title": "Price Comparison API",
        "environment": "production"
    }

@app.get("/test-redirect", tags=["Debug"])
def test_redirect():
    logger.info("🔄 Test redirect endpoint accessed")
    return {"message": "No redirect happening", "status": "ok"}

@app.get("/test-products", tags=["Debug"])
def test_products():
    logger.info("🛍️ Test products endpoint accessed")
    try:
        from app.api.endpoints.products import get_products
        from app.db.session import get_db
        db = next(get_db())
        result = get_products(skip=0, limit=5, db=db)
        logger.info(f"✅ Test products successful: {len(result)} products")
        return {"message": "Products endpoint working", "count": len(result), "status": "ok"}
    except Exception as e:
        logger.error(f"❌ Test products failed: {str(e)}")
        return {"message": "Products endpoint failed", "error": str(e), "status": "error"}