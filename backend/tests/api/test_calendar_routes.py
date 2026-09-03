"""Calendar month API: scoped queries and execution detail."""

from datetime import datetime

import pytest

from bebcare.database import SessionLocal
from bebcare.models import ManualTaskDraft, ScheduledTask, TaskExecution
from bebcare.scheduler.apscheduler_service import scheduler_service
from bebcare.services.ownership import stamp_owner


@pytest.fixture(scope="module", autouse=True)
def apscheduler_paused_for_job_metadata():
    """Populate Job.next_run_time without changing scheduler product code.

    FastAPI TestClient never runs main.py startup, so BackgroundScheduler is
    not started. APScheduler 3.10.4 leaves Job.next_run_time unset until
    start(); production assigns it after scheduler_service.start().
    Start paused so cron does not fire. Do not shutdown: the singleton is
    shared and APScheduler cannot restart after shutdown.
    """
    sched = scheduler_service.scheduler
    if not sched.running:
        sched.start(paused=True)
    yield


def _create_task(full_client, headers, name="Daily post", mode="auto"):
    resp = full_client.post(
        "/v1/tasks/",
        headers=headers,
        json={
            "name": name,
            "cron": "0 10 * * *",
            "mode": mode,
            "enabled": True,
            "platforms": ["instagram"],
            "target_products": [],
            "target_categories": [],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.apscheduler_job_runtime
def test_calendar_month_scoped_and_execution_detail(full_client, auth_headers):
    me = full_client.get("/v1/auth/me", headers=auth_headers).json()
    owner = type("Owner", (), {"user_id": me["user_id"]})()
    task = _create_task(full_client, auth_headers)
    task_id = task["task_id"]

    session = SessionLocal()
    try:
        in_month = datetime(2026, 8, 15, 10, 30, 0)
        other_month = datetime(2026, 7, 20, 10, 30, 0)
        for ex_id, created_at in [("ex-aug", in_month), ("ex-jul", other_month)]:
            ex = TaskExecution(
                execution_id=ex_id,
                task_id=task_id,
                status="SUCCESS",
                generated_images=["https://cdn.example/img.jpg"],
                published_platforms=["instagram"],
                platform_posts=[
                    {
                        "platform": "instagram",
                        "post_link": "https://instagram.com/p/abc",
                    }
                ],
                copywriting="Hello world",
                created_at=created_at,
            )
            stamp_owner(ex, owner)
            session.add(ex)
        session.commit()
    finally:
        session.close()

    res = full_client.get("/v1/tasks/calendar", params={"year": 2026, "month": 8}, headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["year"] == 2026
    assert body["month"] == 8
    assert len(body["executions"]) == 1
    assert body["executions"][0]["execution_id"] == "ex-aug"
    assert body["executions"][0]["thumbnail_url"] == "https://cdn.example/img.jpg"
    assert body["executions"][0]["platform_posts"][0]["post_link"] == "https://instagram.com/p/abc"

    detail = full_client.get("/v1/tasks/executions/ex-aug", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["copywriting"] == "Hello world"
    assert detail.json()["platform_posts"][0]["platform"] == "instagram"


@pytest.mark.apscheduler_job_runtime
def test_calendar_includes_manual_drafts(full_client, auth_headers):
    me = full_client.get("/v1/auth/me", headers=auth_headers).json()
    owner = type("Owner", (), {"user_id": me["user_id"]})()
    task = _create_task(full_client, auth_headers, name="Manual task", mode="manual")
    task_id = task["task_id"]

    session = SessionLocal()
    try:
        draft = ManualTaskDraft(
            draft_id="draft-cal-1",
            task_id=task_id,
            product_id="prod-1",
            images=["https://cdn.example/draft.jpg"],
            copywritings=["Draft copy"],
            status="pending",
            created_at=datetime(2026, 8, 25, 8, 0, 0),
        )
        stamp_owner(draft, owner)
        session.add(draft)
        session.commit()
    finally:
        session.close()

    res = full_client.get("/v1/tasks/calendar", params={"year": 2026, "month": 8}, headers=auth_headers)
    assert res.status_code == 200
    drafts = res.json()["drafts"]
    assert len(drafts) == 1
    assert drafts[0]["draft_id"] == "draft-cal-1"
    assert drafts[0]["thumbnail_url"] == "https://cdn.example/draft.jpg"
    assert drafts[0]["status"] == "pending"


def test_build_platform_posts_from_publish_result():
    from bebcare.services.calendar_service import build_platform_posts_from_publish_result

    platforms, posts = build_platform_posts_from_publish_result(
        {
            "instagram": {
                "success": True,
                "channel": "My IG",
                "post_id": "buf-1",
                "post_link": "https://instagram.com/p/x",
            },
            "tiktok": {"success": False, "error": "nope"},
        }
    )
    assert platforms == ["instagram"]
    assert len(posts) == 1
    assert posts[0]["platform"] == "instagram"
    assert posts[0]["post_link"] == "https://instagram.com/p/x"
