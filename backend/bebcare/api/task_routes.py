from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List
from bebcare.database import get_db
from bebcare.models import ScheduledTask
from bebcare.schemas.task import TaskCreate, TaskUpdate, TaskResponse
from bebcare.scheduler.apscheduler_service import scheduler_service
import uuid

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("/", response_model=TaskResponse, status_code=201)
def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    new_task = ScheduledTask(
        name=task.name,
        cron=task.cron,
        target_categories=task.target_categories,
        target_products=task.target_products,
        platforms=task.platforms,
        reference_image_count=task.reference_image_count,
        run_count_per_execution=task.run_count_per_execution,
        enabled=task.enabled
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    
    if new_task.enabled:
        scheduler_service.add_task(
            str(new_task.task_id),
            new_task.cron,
            new_task.target_categories,
            new_task.target_products,
            new_task.platforms,
            new_task.reference_image_count,
            new_task.run_count_per_execution
        )
    
    return new_task

@router.get("/", response_model=List[TaskResponse])
def list_tasks(db: Session = Depends(get_db)):
    tasks = db.query(ScheduledTask).all()
    return tasks

@router.get("/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(ScheduledTask).filter(ScheduledTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task.task_id,
        "name": task.name,
        "cron": task.cron,
        "target_categories": task.target_categories,
        "target_products": task.target_products,
        "platforms": task.platforms,
        "reference_image_count": task.reference_image_count,
        "run_count_per_execution": task.run_count_per_execution,
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
    
    if task_update.name:
        task.name = task_update.name
    if task_update.cron:
        task.cron = task_update.cron
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
    if task_update.enabled is not None:
        task.enabled = task_update.enabled
    
    if task.enabled:
        scheduler_service.update_task(
            str(task.task_id),
            task.cron,
            task.target_categories,
            task.target_products,
            task.platforms,
            task.reference_image_count,
            task.run_count_per_execution
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
    db.delete(task)
    db.commit()