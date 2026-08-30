from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Boolean, JSON, Index
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
    has_on_body_branding = Column(Boolean, default=True, nullable=False)
    offering_type = Column(String(32), nullable=False, default="unknown")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    brand = relationship("Brand", back_populates="products")
    images = relationship("ProductImage", back_populates="product")

class ProductImage(Base):
    __tablename__ = "product_images"
    __table_args__ = (
        Index("ix_product_images_content_hash", "content_hash"),
        Index("ix_product_images_analysis_status", "analysis_status"),
        Index(
            "ix_product_images_lazy_status_version",
            "analysis_status",
            "deterministic_metadata_version",
        ),
    )
    
    image_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(String(36), ForeignKey("products.product_id", ondelete="CASCADE"))
    cdn_url = Column(String(500), nullable=False)
    phash = Column(String(64))
    width = Column(Integer)
    height = Column(Integer)
    image_type = Column(String(20), nullable=False, default="product")
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    sort_index = Column(Integer, nullable=True)
    is_preferred = Column(Boolean, nullable=False, default=False)
    content_hash = Column(String(64), nullable=True)
    detected_mime_type = Column(String(64), nullable=True)
    has_alpha = Column(Boolean, nullable=True)
    exif_orientation = Column(Integer, nullable=True)
    analysis_status = Column(String(24), nullable=True)
    deterministic_metadata_version = Column(String(32), nullable=True)
    deterministic_metadata_at = Column(DateTime, nullable=True)
    near_duplicate_of_image_id = Column(
        String(36),
        ForeignKey("product_images.image_id", ondelete="SET NULL"),
        nullable=True,
    )
    basic_quality_json = Column(JSON, nullable=True)

    product = relationship("Product", back_populates="images")
