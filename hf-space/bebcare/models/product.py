from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Boolean
from sqlalchemy.orm import relationship
from bebcare.database import Base
from bebcare.models.ownership import OwnedMixin
import uuid
from datetime import datetime

class Product(OwnedMixin, Base):
    __tablename__ = "products"
    
    product_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_name = Column(String(255), nullable=False)
    brand_id = Column(
        String(36),
        ForeignKey("brands.brand_id", ondelete="SET NULL"),
        nullable=True,
    )
    category = Column(String(100), nullable=False)
    description = Column(Text)
    selling_points = Column(String(500))
    brand_voice = Column(Text)  # legacy; prefer brand.voice + optional override
    use_brand_voice = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    brand = relationship("Brand", back_populates="products")
    images = relationship("ProductImage", back_populates="product")

class ProductImage(Base):
    __tablename__ = "product_images"
    
    image_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(String(36), ForeignKey("products.product_id", ondelete="CASCADE"))
    cdn_url = Column(String(500), nullable=False)
    phash = Column(String(64))
    width = Column(Integer)
    height = Column(Integer)
    image_type = Column(String(20), nullable=False, default="product")
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    product = relationship("Product", back_populates="images")
