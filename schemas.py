from pydantic import BaseModel, validator, field_validator, EmailStr
from typing import Optional, List
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    full_name: str

class UserCreate(UserBase):
    password: str

    @field_validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        if len(v) > 72:
            raise ValueError('Password must be less than 72 characters')
        return v

class User(UserBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True

class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    sku: str
    min_stock: int = 0
    max_stock: int = 1000

    @field_validator('sku')
    def validate_sku(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('SKU cannot be empty')
        return v.strip()

    @field_validator('min_stock', 'max_stock')
    def validate_stock_values(cls, v, info):
        if v < 0:
            raise ValueError('Stock values cannot be negative')
        return v

class ProductCreate(ProductBase):
    pass

class Product(ProductBase):
    id: int
    current_stock: int = 0
    created_at: datetime
    user_id: int

    class Config:
        from_attributes = True

class SupplyBase(BaseModel):
    product_id: int
    quantity: int
    supplier: str

    @field_validator('quantity')
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError('Quantity must be positive')
        return v

class SupplyCreate(SupplyBase):
    pass

class Supply(SupplyBase):
    id: int
    supply_date: datetime
    status: str
    user_id: int

    class Config:
        from_attributes = True

class InventoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    status: Optional[str] = "pending"
    is_successful: Optional[bool] = False
    comment: Optional[str] = None

class InventoryCreate(InventoryBase):
    pass

class Inventory(InventoryBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    user_id: int

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class InventoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    is_successful: Optional[bool] = None
    comment: Optional[str] = None