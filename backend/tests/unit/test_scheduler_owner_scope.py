from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from bebcare.database import Base
import bebcare.models  # noqa: F401 — register metadata
from bebcare.models import Product, ScheduledTask, TaskExecution, User
from bebcare.scheduler.apscheduler_service import _task_owner, products_for_task
from bebcare.services.ownership import stamp_owner


def _memory_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(bind=engine)


def _seed_users_and_products(session: Session) -> ScheduledTask:
    session.add_all(
        [
            User(
                user_id="user-a",
                username="owner-a",
                email="a@test.local",
                hashed_password="x",
            ),
            User(
                user_id="user-b",
                username="owner-b",
                email="b@test.local",
                hashed_password="x",
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            Product(
                product_id="prod-a",
                product_name="Owner A Product",
                category="toys",
                owner_user_id="user-a",
            ),
            Product(
                product_id="prod-b",
                product_name="Owner B Product",
                category="toys",
                owner_user_id="user-b",
            ),
        ]
    )
    task = ScheduledTask(
        task_id="task-a",
        name="Owner A job",
        cron="0 9 * * *",
        owner_user_id="user-a",
        target_products=["prod-a", "prod-b"],
        target_categories=[],
    )
    session.add(task)
    session.commit()
    return task


def test_scheduler_products_match_task_owner():
    session = _memory_session()
    try:
        task = _seed_users_and_products(session)
        result = products_for_task(session, task)
        assert [p.product_id for p in result] == ["prod-a"]
    finally:
        session.close()


def test_scheduler_products_by_category_exclude_other_owner():
    session = _memory_session()
    try:
        task = _seed_users_and_products(session)
        task.target_products = []
        task.target_categories = ["toys"]
        session.commit()
        result = products_for_task(session, task)
        assert [p.product_id for p in result] == ["prod-a"]
    finally:
        session.close()


def test_task_execution_stamped_with_task_owner():
    session = _memory_session()
    try:
        task = _seed_users_and_products(session)
        execution = TaskExecution(
            execution_id="exec-1",
            task_id=task.task_id,
            product_id="prod-a",
            status="RUNNING",
        )
        stamp_owner(execution, _task_owner(task))
        session.add(execution)
        session.commit()
        row = session.query(TaskExecution).filter(
            TaskExecution.execution_id == "exec-1"
        ).first()
        assert row.owner_user_id == "user-a"
        assert row.workspace_id is None
    finally:
        session.close()
