from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
from datetime import datetime
import pytz

moscow_tz = pytz.timezone('Europe/Moscow')

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    products = relationship("Product", back_populates="user", cascade="all, delete-orphan")
    supplies = relationship("Supply", back_populates="user", cascade="all, delete-orphan")
    inventories = relationship("Inventory", back_populates="user", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(Text)
    sku = Column(String, unique=True, index=True, nullable=False)
    current_stock = Column(Integer, default=0)
    min_stock = Column(Integer, default=0)
    max_stock = Column(Integer, default=1000)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    user = relationship("User", back_populates="products")
    supplies = relationship("Supply", back_populates="product", cascade="all, delete-orphan")


class Supply(Base):
    __tablename__ = "supplies"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"))
    quantity = Column(Integer, nullable=False)
    supplier = Column(String, nullable=False)
    supply_date = Column(DateTime(timezone=True), default=lambda: datetime.now(moscow_tz))
    status = Column(String, default="received")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    product = relationship("Product", back_populates="supplies")
    user = relationship("User", back_populates="supplies")


class Inventory(Base):
    __tablename__ = "inventories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="pending")
    is_successful = Column(Boolean, default=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(moscow_tz))
    updated_at = Column(DateTime(timezone=True), onupdate=lambda: datetime.now(moscow_tz))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    user = relationship("User", back_populates="inventories")