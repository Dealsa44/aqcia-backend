from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.schemas.product_schemas import Product, ProductCreate
from app.db.models import Product as ProductModel
from app.utils.auth import get_current_user
from celery_worker import notify_user
from app.db import session as db_session, models
from app.schemas import product_schemas

router = APIRouter()

@router.post("/", response_model=product_schemas.Product)
def create_or_update_product(product: product_schemas.ProductCreate, db: Session = Depends(db_session.get_db)):
    # Prefer matching by api_product_id when provided; otherwise fall back to name/brand/bar_code
    product_data = product.dict(exclude_unset=True)
    db_product = None
    api_product_id = product_data.get("api_product_id")
    if api_product_id is not None:
        db_product = db.query(models.Product).filter_by(api_product_id=api_product_id).first()
    if db_product is None:
        db_product = (
            db.query(models.Product)
            .filter_by(name=product_data.get("name"), brand=product_data.get("brand"), bar_code=product_data.get("bar_code"))
            .first()
        )
    if db_product:
        for field, value in product_data.items():
            setattr(db_product, field, value)
    else:
        allowed_fields = {"name", "brand", "api_product_id", "bar_code", "image_url", "subcategory_id"}
        new_product_kwargs = {k: v for k, v in product_data.items() if k in allowed_fields}
        db_product = models.Product(**new_product_kwargs)
        db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

@router.get("/", response_model=List[product_schemas.Product])
def get_products(skip: int = 0, limit: int = 100, db: Session = Depends(db_session.get_db)):
    return db.query(models.Product).offset(skip).limit(limit).all()

@router.get("/{product_id}", response_model=Product)
def get_product(
    product_id: int,
    db: Session = Depends(db_session.get_db),
    current_user = Depends(get_current_user)  # <-- Also protected
):
    product = db.query(ProductModel).filter(ProductModel.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.delete("/{product_id}", response_model=dict)
def delete_product(
    product_id: int,
    db: Session = Depends(db_session.get_db),
    current_user = Depends(get_current_user)  # <-- Also protected
):
    product = db.query(ProductModel).filter(ProductModel.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
    return {"detail": "Product deleted"}
