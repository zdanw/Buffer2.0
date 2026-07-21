from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional
from bebcare.database import get_db
from bebcare.models import PublishRecord
from bebcare.publisher.buffer_publisher import buffer_publisher
import uuid
from datetime import datetime

router = APIRouter(prefix="/publish", tags=["publish"])

@router.post("/")
def publish_content(
    text: str,
    image_url: Optional[str] = None,
    platforms: list = None,
    db: Session = Depends(get_db)
):
    if platforms is None:
        platforms = ["instagram", "tiktok", "facebook"]
    
    publish_record = PublishRecord(
        publish_id=uuid.uuid4(),
        content={"text": text, "image_url": image_url},
        status="pending"
    )
    db.add(publish_record)
    db.commit()
    db.refresh(publish_record)
    
    for platform in platforms:
        result = buffer_publisher.publish(text, image_url, [platform])
        
        platform_record = PublishRecord(
            publish_id=uuid.uuid4(),
            platform=platform,
            content={"text": text, "image_url": image_url},
            status="completed" if result.get("success") else "failed",
            buffer_id=result.get("data", {}).get("id")
        )
        db.add(platform_record)
    
    db.commit()
    
    return {"publish_id": str(publish_record.publish_id), "status": "completed"}

@router.get("/status/{publish_id}")
def get_publish_status(publish_id: UUID, db: Session = Depends(get_db)):
    record = db.query(PublishRecord).filter(PublishRecord.publish_id == publish_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Publish record not found")
    return record