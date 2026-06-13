import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from bebcare.database import get_db
from bebcare.models import ProductImage
from bebcare.knowledge_base.chroma_client import chroma_client
from bebcare.utils.image_utils import download_image, calculate_phash

def migrate_embeddings():
    print("=== Starting embedding migration ===")
    
    try:
        chroma_client.reset_collection()
        print("ChromaDB collection reset")
        
        db = next(get_db())
        images = db.query(ProductImage).all()
        
        print(f"Found {len(images)} images to migrate")
        
        success_count = 0
        fail_count = 0
        
        for i, image in enumerate(images, 1):
            print(f"\nProcessing image {i}/{len(images)}: {image.image_id}")
            print(f"  CDN URL: {image.cdn_url}")
            
            try:
                img = download_image(image.cdn_url)
                print(f"  Downloaded successfully")
                
                embedding = chroma_client.get_image_embedding(img)
                print(f"  Generated embedding: {len(embedding)} dimensions")
                
                phash = calculate_phash(img)
                print(f"  Calculated phash: {phash}")
                
                chroma_client.add_image(
                    str(image.image_id),
                    embedding,
                    {
                        "product_id": str(image.product_id),
                        "image_id": str(image.image_id),
                        "cdn_url": image.cdn_url,
                        "phash": phash,
                        "image_type": image.image_type,
                        "created_at": str(image.uploaded_at)
                    }
                )
                print(f"  Added to ChromaDB successfully")
                success_count += 1
                
            except Exception as e:
                print(f"  FAILED: {str(e)}")
                fail_count += 1
        
        print(f"\n=== Migration Complete ===")
        print(f"Success: {success_count}")
        print(f"Failed: {fail_count}")
        
    except Exception as e:
        print(f"Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    migrate_embeddings()