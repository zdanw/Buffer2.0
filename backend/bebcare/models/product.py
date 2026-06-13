from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from bebcare.database import Base
import uuid
from datetime import datetime

class Product(Base):
    __tablename__ = "products"
    
    product_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(Text)
    tags = Column(String(500))
    brand_voice = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    images = relationship("ProductImage", back_populates="product")

class ProductImage(Base):
    __tablename__ = "product_images"
    
    image_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(String(36), ForeignKey("products.product_id"))
    cdn_url = Column(String(500), nullable=False)
    phash = Column(String(64))
    width = Column(Integer)
    height = Column(Integer)
    image_type = Column(String(20), nullable=False, default="product")
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    product = relationship("Product", back_populates="images")
