from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from bebcare.database import get_db
from bebcare.models import Product, ProductImage
from bebcare.schemas.product import ProductCreate, ProductUpdate, ProductResponse, ImageUploadResponse
from bebcare.knowledge_base.chroma_client import chroma_client
from bebcare.utils.image_utils import calculate_phash, get_image_dimensions, download_image
from bebcare.utils.github_uploader import github_uploader
import uuid
import io

router = APIRouter(prefix="/products", tags=["products"])

@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    """获取所有产品分类列表"""
    categories = db.query(Product.category).distinct().all()
    category_list = [cat[0] for cat in categories if cat[0]]
    return {"categories": category_list}

@router.get("/")
def list_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    result = []
    for product in products:
        images = db.query(ProductImage).filter(ProductImage.product_id == product.product_id).all()
        
        product_images = []
        scene_images = []
        
        for img in images:
            img_dict = {
                "image_id": img.image_id,
                "cdn_url": img.cdn_url,
                "phash": img.phash,
                "width": img.width,
                "height": img.height,
                "image_type": img.image_type,
                "uploaded_at": img.uploaded_at
            }
            if img.image_type == "product":
                product_images.append(img_dict)
            else:
                scene_images.append(img_dict)
        
        product_dict = {
            "product_id": product.product_id,
            "product_name": product.product_name,
            "category": product.category,
            "description": product.description,
            "selling_points": product.selling_points.split(",") if product.selling_points else [],
            "brand_voice": product.brand_voice,
            "created_at": product.created_at,
            "updated_at": product.updated_at,
            "product_images": product_images,
            "scene_images": scene_images
        }
        result.append(product_dict)
    return result

@router.post("/", status_code=201)
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    new_product = Product(
        product_name=product.product_name,
        category=product.category,
        description=product.description,
        selling_points=",".join(product.selling_points) if product.selling_points else None,
        brand_voice=product.brand_voice
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    
    return {
        "product_id": new_product.product_id,
        "product_name": new_product.product_name,
        "category": new_product.category,
        "description": new_product.description,
        "selling_points": product.selling_points or [],
        "brand_voice": new_product.brand_voice,
        "created_at": new_product.created_at,
        "updated_at": new_product.updated_at,
        "product_images": [],
        "scene_images": []
    }

@router.get("/{product_id}")
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    images = db.query(ProductImage).filter(ProductImage.product_id == product_id).all()
    
    product_images = []
    scene_images = []
    
    for img in images:
        img_dict = {
            "image_id": img.image_id,
            "cdn_url": img.cdn_url,
            "phash": img.phash,
            "width": img.width,
            "height": img.height,
            "image_type": img.image_type,
            "uploaded_at": img.uploaded_at
        }
        if img.image_type == "product":
            product_images.append(img_dict)
        else:
            scene_images.append(img_dict)
    
    return {
        "product_id": product.product_id,
        "product_name": product.product_name,
        "category": product.category,
        "description": product.description,
        "selling_points": product.selling_points.split(",") if product.selling_points else [],
        "brand_voice": product.brand_voice,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
        "product_images": product_images,
        "scene_images": scene_images
    }
@router.put("/{product_id}")
def update_product(product_id: str, product_update: ProductUpdate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    if product_update.product_name:
        product.product_name = product_update.product_name
    if product_update.category:
        product.category = product_update.category
    if product_update.description:
        product.description = product_update.description
    if product_update.selling_points:
        product.selling_points = ",".join(product_update.selling_points)
    if product_update.brand_voice:
        product.brand_voice = product_update.brand_voice
    
    db.commit()
    db.refresh(product)
    
    images = db.query(ProductImage).filter(ProductImage.product_id == product_id).all()
    
    product_images = []
    scene_images = []
    
    for img in images:
        img_dict = {
            "image_id": img.image_id,
            "cdn_url": img.cdn_url,
            "phash": img.phash,
            "width": img.width,
            "height": img.height,
            "image_type": img.image_type,
            "uploaded_at": img.uploaded_at
        }
        if img.image_type == "product":
            product_images.append(img_dict)
        else:
            scene_images.append(img_dict)
    
    return {
        "product_id": product.product_id,
        "product_name": product.product_name,
        "category": product.category,
        "description": product.description,
        "selling_points": product.selling_points.split(",") if product.selling_points else [],
        "brand_voice": product.brand_voice,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
        "product_images": product_images,
        "scene_images": scene_images
    }
@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    db.delete(product)
    db.commit()

@router.post("/{product_id}/images", response_model=ImageUploadResponse)
def upload_product_images(
    product_id: str,
    files: Optional[List[UploadFile]] = File(None),
    image_urls: Optional[str] = None,
    image_type: str = "product",
    db: Session = Depends(get_db)
):
    if image_type not in ["product", "scene"]:
        raise HTTPException(status_code=400, detail="Invalid image_type. Must be 'product' or 'scene'")
    
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    uploaded = []
    
    if files:
        for file in files:
            try:
                print(f"Processing file: {file.filename}")
                
                file_content = file.file.read()
                print(f"File size: {len(file_content)} bytes")
                
                cdn_url = github_uploader.upload_file(file_content, file.filename)
                print(f"Uploaded to CDN: {cdn_url}")
                
                image = download_image(cdn_url)
                print("Downloaded image successfully")
                
                phash = calculate_phash(image)
                width, height = get_image_dimensions(image)
                print(f"Image dimensions: {width}x{height}, phash: {phash}")
                
                embedding = chroma_client.get_image_embedding(image)
                print(f"Generated embedding with {len(embedding)} dimensions")
                
                new_image = ProductImage(
                    product_id=product_id,
                    cdn_url=cdn_url,
                    phash=phash,
                    width=width,
                    height=height,
                    image_type=image_type
                )
                db.add(new_image)
                db.flush()
                
                chroma_client.add_image(
                    str(new_image.image_id),
                    embedding,
                    {
                        "product_id": str(product_id),
                        "image_id": str(new_image.image_id),
                        "product_name": product.product_name,
                        "category": product.category,
                        "description": product.description,
                        "cdn_url": cdn_url,
                        "phash": phash,
                        "selling_points": product.selling_points,
                        "image_type": image_type,
                        "created_at": str(new_image.uploaded_at)
                    }
                )
                
                uploaded.append({
                    "image_id": str(new_image.image_id),
                    "cdn_url": cdn_url,
                    "phash": phash,
                    "width": width,
                    "height": height,
                    "image_type": image_type
                })
                print(f"Image {file.filename} processed successfully")
                
            except Exception as e:
                print(f"Error processing file {file.filename}: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to upload image {file.filename}: {str(e)}")
    
    db.commit()
    
    return {"product_id": product_id, "uploaded": uploaded}

@router.get("/{product_id}/images")
def get_product_images(product_id: str, db: Session = Depends(get_db)):
    images = db.query(ProductImage).filter(ProductImage.product_id == product_id).all()
    return {"product_id": product_id, "images": images}

@router.delete("/{product_id}/images/{image_id}", status_code=204)
def delete_product_image(product_id: str, image_id: str, db: Session = Depends(get_db)):
    image = db.query(ProductImage).filter(
        ProductImage.product_id == product_id,
        ProductImage.image_id == image_id
    ).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    chroma_client.delete_image(image_id)
    db.delete(image)
    db.commit()