from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional
from bebcare.database import get_db
from bebcare.models import ScheduledTask, TaskExecution, ManualTaskDraft
from bebcare.schemas.task import TaskCreate, TaskUpdate, TaskResponse, ManualTaskDraftResponse, DraftPublishRequest
from bebcare.scheduler.apscheduler_service import scheduler_service
from bebcare.publisher.buffer_publisher import buffer_publisher
from bebcare.utils.github_uploader import github_uploader
from bebcare.utils.image_utils import download_image
import uuid
import json
from io import BytesIO

def validate_cron(cron: str):
    fields = cron.split()
    if len(fields) != 5:
        raise HTTPException(status_code=400, detail=f"CRON表达式格式错误，需要5个字段，当前有{len(fields)}个")

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("/", response_model=TaskResponse, status_code=201)
def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    validate_cron(task.cron)
    new_task = ScheduledTask(
        name=task.name,
        cron=task.cron,
        mode=task.mode,
        target_categories=task.target_categories,
        target_products=task.target_products,
        platforms=task.platforms,
        reference_image_count=task.reference_image_count,
        run_count_per_execution=task.run_count_per_execution,
        generate_image_count=task.generate_image_count,
        generate_copy_count=task.generate_copy_count,
        enabled=task.enabled,
        use_scene_reference=task.use_scene_reference
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    
    if new_task.enabled:
        scheduler_service.add_task(
            str(new_task.task_id),
            new_task.mode,
            new_task.cron,
            new_task.target_categories,
            new_task.target_products,
            new_task.platforms,
            new_task.reference_image_count,
            new_task.run_count_per_execution,
            new_task.generate_image_count,
            new_task.generate_copy_count,
            new_task.use_scene_reference
        )
    
    return new_task

@router.get("/")
def list_tasks(
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db)
):
    query = db.query(ScheduledTask)
    total = query.count()
    
    offset = (page - 1) * page_size
    tasks = query.order_by(ScheduledTask.created_at.desc()).offset(offset).limit(page_size).all()
    
    return {
        "data": tasks,
        "pagination": {
            "current": page,
            "page_size": page_size,
            "total": total,
            "pages": (total + page_size - 1) // page_size
        }
    }

@router.get("/drafts/")
def get_drafts(
    status: Optional[str] = "pending",
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db)
):
    try:
        query = db.query(ManualTaskDraft)
        if status:
            query = query.filter(ManualTaskDraft.status == status)
        
        total = query.count()
        offset = (page - 1) * page_size
        drafts = query.order_by(ManualTaskDraft.created_at.desc()).offset(offset).limit(page_size).all()
        
        result = []
        for draft in drafts:
            try:
                images = json.loads(draft.images) if isinstance(draft.images, str) else (draft.images or [])
            except (json.JSONDecodeError, TypeError):
                images = []
            
            try:
                copywritings = json.loads(draft.copywritings) if isinstance(draft.copywritings, str) else (draft.copywritings or [])
            except (json.JSONDecodeError, TypeError):
                copywritings = []
            
            try:
                published_platforms = json.loads(draft.published_platforms) if isinstance(draft.published_platforms, str) else (draft.published_platforms or [])
            except (json.JSONDecodeError, TypeError):
                published_platforms = []

            try:
                dimensions = json.loads(draft.dimensions) if isinstance(draft.dimensions, str) else (draft.dimensions or [])
            except (json.JSONDecodeError, TypeError):
                dimensions = []

            try:
                image_prompts = json.loads(draft.image_prompts) if isinstance(draft.image_prompts, str) else (draft.image_prompts or [])
            except (json.JSONDecodeError, TypeError):
                image_prompts = []
            
            result.append({
                "draft_id": draft.draft_id,
                "task_id": draft.task_id,
                "product_id": draft.product_id,
                "images": images,
                "copywritings": copywritings,
                "dimensions": dimensions,
                "image_prompts": image_prompts,
                "status": draft.status,
                "selected_image": draft.selected_image,
                "selected_copy": draft.selected_copy,
                "published_platforms": published_platforms,
                "created_at": draft.created_at
            })
        
        return {
            "data": result,
            "pagination": {
                "current": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load drafts: {str(e)}")

@router.post("/drafts/{draft_id}/publish/")
def publish_draft(draft_id: str, request: DraftPublishRequest, db: Session = Depends(get_db)):
    draft = db.query(ManualTaskDraft).filter(ManualTaskDraft.draft_id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    if draft.status != "pending":
        raise HTTPException(status_code=400, detail="Draft is not pending")
    
    images = json.loads(draft.images) if isinstance(draft.images, str) else draft.images
    copywritings = json.loads(draft.copywritings) if isinstance(draft.copywritings, str) else draft.copywritings
    
    if request.selected_image_index >= len(images) or request.selected_image_index < 0:
        raise HTTPException(status_code=400, detail="Invalid image index")
    
    if request.selected_copy_index >= len(copywritings) or request.selected_copy_index < 0:
        raise HTTPException(status_code=400, detail="Invalid copy index")
    
    selected_image = images[request.selected_image_index]
    selected_copy = copywritings[request.selected_copy_index]
    
    try:
        image = download_image(selected_image)
        if image:
            buffer = BytesIO()
            image.save(buffer, format='JPEG')
            buffer.seek(0)
            import datetime
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            cdn_url = github_uploader.upload_file(buffer, f"draft_{draft_id}_{timestamp}.jpg")
            
            publish_result = buffer_publisher.publish(selected_copy, cdn_url, request.platforms)
            
            success_platforms = []
            for platform, result in publish_result.items():
                if result.get("success"):
                    success_platforms.append(platform)
            
            draft.status = "published"
            draft.selected_image = cdn_url
            draft.selected_copy = selected_copy
            draft.published_platforms = success_platforms
            
            db.commit()
            
            return {
                "success": True,
                "draft_id": draft_id,
                "published_platforms": success_platforms,
                "cdn_url": cdn_url
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to download image")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Publish failed: {str(e)}")

@router.post("/drafts/{draft_id}/discard/")
def discard_draft(draft_id: str, db: Session = Depends(get_db)):
    draft = db.query(ManualTaskDraft).filter(ManualTaskDraft.draft_id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    
    if draft.status != "pending":
        raise HTTPException(status_code=400, detail="Draft is not pending")
    
    draft.status = "discarded"
    db.commit()
    
    return {"success": True, "draft_id": draft_id}

@router.get("/executions")
def get_all_executions(db: Session = Depends(get_db)):
    executions = db.query(TaskExecution).order_by(TaskExecution.created_at.desc()).all()
    return executions

@router.get("/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(ScheduledTask).filter(ScheduledTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task.task_id,
        "name": task.name,
        "cron": task.cron,
        "mode": task.mode,
        "target_categories": task.target_categories,
        "target_products": task.target_products,
        "platforms": task.platforms,
        "reference_image_count": task.reference_image_count,
        "run_count_per_execution": task.run_count_per_execution,
        "generate_image_count": task.generate_image_count,
        "generate_copy_count": task.generate_copy_count,
        "enabled": task.enabled,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "last_run_at": task.last_run_at,
        "next_run_at": task.next_run_at
    }

@router.put("/{task_id}")
def update_task(task_id: str, task_update: TaskUpdate, db: Session = Depends(get_db)):
    task = db.query(ScheduledTask).filter(ScheduledTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task_update.cron:
        validate_cron(task_update.cron)
    
    if task_update.name:
        task.name = task_update.name
    if task_update.cron:
        task.cron = task_update.cron
    if task_update.mode:
        task.mode = task_update.mode
    if task_update.target_categories:
        task.target_categories = task_update.target_categories
    if task_update.target_products:
        task.target_products = task_update.target_products
    if task_update.platforms:
        task.platforms = task_update.platforms
    if task_update.reference_image_count:
        task.reference_image_count = task_update.reference_image_count
    if task_update.run_count_per_execution:
        task.run_count_per_execution = task_update.run_count_per_execution
    if task_update.generate_image_count:
        task.generate_image_count = task_update.generate_image_count
    if task_update.generate_copy_count:
        task.generate_copy_count = task_update.generate_copy_count
    if task_update.enabled is not None:
        task.enabled = task_update.enabled
    if task_update.use_scene_reference is not None:
        task.use_scene_reference = task_update.use_scene_reference
    
    if task.enabled:
        scheduler_service.update_task(
            str(task.task_id),
            task.mode,
            task.cron,
            task.target_categories,
            task.target_products,
            task.platforms,
            task.reference_image_count,
            task.run_count_per_execution,
            task.generate_image_count,
            task.generate_copy_count,
            task.use_scene_reference
        )
    else:
        scheduler_service.remove_task(task_id)
    
    db.commit()
    db.refresh(task)
    return task

@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(ScheduledTask).filter(ScheduledTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    scheduler_service.remove_task(task_id)
    
    db.query(ManualTaskDraft).filter(ManualTaskDraft.task_id == task_id).delete(synchronize_session=False)
    db.query(TaskExecution).filter(TaskExecution.task_id == task_id).delete(synchronize_session=False)
    
    db.delete(task)
    db.commit()

@router.get("/{task_id}/executions")
def get_task_executions(task_id: str, db: Session = Depends(get_db)):
    executions = db.query(TaskExecution).filter(
        TaskExecution.task_id == task_id
    ).order_by(TaskExecution.created_at.desc()).all()
    return executions
