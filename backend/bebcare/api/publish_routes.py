from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional
from bebcare.database import get_db
from bebcare.models import PublishRecord, Product, Brand
from bebcare.models.user import User
from bebcare.publisher.buffer_publisher import buffer_publisher
from bebcare.services.auth_dependency import get_current_active_user
from bebcare.services.buffer_account_service import (
    resolve_buffer_api_token,
    BufferAccountUnavailable,
)
from bebcare.services.ownership import assert_owned_ref, get_owned_or_404, stamp_owner
import uuid
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/publish", tags=["publish"])


class PublishRequest(BaseModel):
    text: str = Field(..., min_length=1)
    image_url: Optional[str] = None
    platforms: Optional[List[str]] = None
    product_id: Optional[str] = None
    brand_id: Optional[str] = None


@router.post("/")
def publish_content(
    request: PublishRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="文案不能为空")

    platforms = request.platforms or ["instagram", "tiktok", "facebook"]
    platforms = [p for p in platforms if p]
    if not platforms:
        raise HTTPException(status_code=400, detail="请至少选择一个发布平台")

    assert_owned_ref(db, Product, request.product_id, current_user, id_attr="product_id")
    assert_owned_ref(db, Brand, request.brand_id, current_user, id_attr="brand_id")

    image_url = (request.image_url or "").strip() or None
    publish_id = str(uuid.uuid4())

    publish_record = PublishRecord(
        publish_id=publish_id,
        content={"text": text, "image_url": image_url},
        status="pending",
    )
    stamp_owner(publish_record, current_user)
    db.add(publish_record)
    db.commit()
    db.refresh(publish_record)

    try:
        api_token = resolve_buffer_api_token(
            db,
            product_id=request.product_id,
            brand_id=request.brand_id,
            owner_user_id=current_user.user_id,
        )
    except BufferAccountUnavailable as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    if not api_token:
        raise HTTPException(
            status_code=400,
            detail="未绑定 Buffer 账户。请到「品牌管理」为该品牌绑定 Buffer 账户后再发布。",
        )

    results = buffer_publisher.publish(text, image_url, platforms, api_token=api_token)
    success_platforms: List[str] = []
    failed: dict = {}

    for platform in platforms:
        platform_result = results.get(platform) or {}
        ok = bool(platform_result.get("success"))
        if ok:
            success_platforms.append(platform)
        else:
            failed[platform] = platform_result.get("error") or "publish failed"

        platform_record = PublishRecord(
            publish_id=str(uuid.uuid4()),
            platform=platform,
            content={"text": text, "image_url": image_url},
            status="completed" if ok else "failed",
            buffer_id=platform_result.get("post_id"),
            published_at=datetime.utcnow() if ok else None,
        )
        stamp_owner(platform_record, current_user)
        db.add(platform_record)

    publish_record.status = "completed" if success_platforms else "failed"
    publish_record.published_at = datetime.utcnow() if success_platforms else None
    db.commit()

    if not success_platforms:
        logger.error("Publish failed for all platforms: %s", failed)
        raise HTTPException(status_code=502, detail=f"发布失败: {failed}")

    return {
        "publish_id": publish_id,
        "status": "completed",
        "published_platforms": success_platforms,
        "failed": failed or None,
    }


@router.get("/status/{publish_id}")
def get_publish_status(
    publish_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    record = get_owned_or_404(
        db, PublishRecord, str(publish_id), current_user, id_attr="publish_id"
    )
    return record
