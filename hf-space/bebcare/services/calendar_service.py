"""Helpers for month-scoped publish calendar API."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from bebcare.models import ManualTaskDraft, ScheduledTask, TaskExecution


def _json_field(value: Any, default: Any = None):
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default
    return value


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    """month is 1–12 (calendar month)."""
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return start, end


def _task_name_map(tasks: List[ScheduledTask]) -> Dict[str, str]:
    return {str(t.task_id): t.name for t in tasks}


def execution_summary(
    execution: TaskExecution, task_names: Dict[str, str]
) -> Dict[str, Any]:
    images = _json_field(execution.generated_images, [])
    platform_posts = _json_field(execution.platform_posts, [])
    published_platforms = _json_field(execution.published_platforms, [])
    task_id = str(execution.task_id) if execution.task_id else None
    return {
        "execution_id": execution.execution_id,
        "task_id": task_id,
        "task_name": task_names.get(task_id or "", "Unknown task"),
        "product_id": execution.product_id,
        "status": execution.status,
        "created_at": execution.created_at,
        "thumbnail_url": images[0] if images else None,
        "published_platforms": published_platforms,
        "platform_posts": platform_posts,
    }


def draft_summary(draft: ManualTaskDraft, task_names: Dict[str, str]) -> Dict[str, Any]:
    images = _json_field(draft.images, [])
    copywritings = _json_field(draft.copywritings, [])
    platform_posts = _json_field(draft.platform_posts, [])
    published_platforms = _json_field(draft.published_platforms, [])
    task_id = str(draft.task_id) if draft.task_id else None
    copy_preview = None
    if draft.status == "published" and draft.selected_copy:
        copy_preview = str(draft.selected_copy)[:160]
    elif copywritings:
        copy_preview = str(copywritings[0])[:160]
    thumb = None
    if draft.status == "published" and draft.selected_image:
        thumb = draft.selected_image
    elif images:
        thumb = images[0]
    return {
        "draft_id": draft.draft_id,
        "task_id": task_id,
        "task_name": task_names.get(task_id or "", "Unknown task"),
        "product_id": draft.product_id,
        "status": draft.status,
        "created_at": draft.created_at,
        "thumbnail_url": thumb,
        "copy_preview": copy_preview,
        "published_platforms": published_platforms,
        "platform_posts": platform_posts,
    }


def serialize_execution_detail(execution: TaskExecution) -> Dict[str, Any]:
    return {
        "execution_id": execution.execution_id,
        "task_id": execution.task_id,
        "product_id": execution.product_id,
        "status": execution.status,
        "error_message": execution.error_message,
        "generated_images": _json_field(execution.generated_images, []),
        "published_platforms": _json_field(execution.published_platforms, []),
        "platform_posts": _json_field(execution.platform_posts, []),
        "copywriting": execution.copywriting,
        "dimensions": _json_field(execution.dimensions),
        "image_prompt": execution.image_prompt,
        "reference_product_images": _json_field(execution.reference_product_images, []),
        "reference_scene_images": _json_field(execution.reference_scene_images, []),
        "created_at": execution.created_at,
    }


def build_platform_posts_from_publish_result(publish_result: dict) -> tuple[list, list]:
    """Return (success_platform_names, platform_posts) from buffer_publisher.publish()."""
    success_platforms: List[str] = []
    platform_posts: List[dict] = []
    for platform_name, pub in publish_result.items():
        if pub.get("success"):
            success_platforms.append(platform_name)
            platform_posts.append(
                {
                    "platform": platform_name,
                    "channel": pub.get("channel"),
                    "post_id": pub.get("post_id"),
                    "post_link": pub.get("post_link") or pub.get("external_link"),
                }
            )
    return success_platforms, platform_posts
