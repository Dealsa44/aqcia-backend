from pydantic import BaseModel
from typing import Optional

class ProductResponse(BaseModel):
    product_id: int
    name: str
    brand: str
    price: float
    sale_price: Optional[float]
    is_on_sale: bool
    available_quantity: int

    model_config = {"from_attributes": True}

class CategoryBase(BaseModel):
    name: str
    name_ka: str
    name_en: str
    name_ru: str
    icon: Optional[str] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(CategoryBase):
    pass

class CategoryOut(CategoryBase):
    id: int
    
    model_config = {"from_attributes": True}

# --- Subcategory Schemas ---

class SubcategoryBase(BaseModel):
    name: str
    name_ka: Optional[str] = None
    name_en: Optional[str] = None
    name_ru: Optional[str] = None
    icon: Optional[str] = None
    category_id: int

class SubcategoryCreate(SubcategoryBase):
    pass

class SubcategoryUpdate(BaseModel):
    name: Optional[str] = None
    name_ka: Optional[str] = None
    name_en: Optional[str] = None
    name_ru: Optional[str] = None
    icon: Optional[str] = None
    category_id: Optional[int] = None

class SubcategoryOut(SubcategoryBase):
    id: int
    
    model_config = {"from_attributes": True}
