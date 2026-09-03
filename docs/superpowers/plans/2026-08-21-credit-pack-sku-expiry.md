# Credit Pack SKU + 30-Day Expiry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Stripe 一次性 SKU 调整为 Basic/Pro/Super（30/120/300），并为 Stripe grant 增加 30 天过期 + 定时清零。

**Architecture:** `image_credit_grants.expires_at`；`remaining_credits`/`reserve_one` 排除过期并 FEFO；Stripe fulfill 写入 `now+30d`；APScheduler interval 调用 `expire_due_grants`；SKU 仍经 `STRIPE_CREDIT_PACKS`（金额在 Stripe Dashboard）。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、APScheduler、pytest、React i18n。

**Spec:** [`docs/superpowers/specs/2026-08-21-credit-pack-sku-expiry-design.md`](../specs/2026-08-21-credit-pack-sku-expiry-design.md)

## Global Constraints

- 仍为一次性 Checkout；不做订阅。
- 金额不进代码；仅 `price_id` / `credits` / `label`。
- 仅 Stripe grant 默认 30 天过期；试用 / admin `expires_at=NULL`。
- 改 `backend/` 后跑 `python scripts/sync_deploy_copies.py`。
- 测试：`cd backend && python -m pytest … -v`
- 不提交含真实 `price_id` / 密钥的 `.env`。

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/migrations/versions/027_grant_expires_at.py` | 加 `expires_at` |
| `backend/bebcare/models/image_credit.py` | 模型列 |
| `backend/bebcare/config/settings.py` | 过期天数 / 清零间隔 |
| `backend/bebcare/services/credit_grant_service.py` | 创建/余额/FEFO/清零 |
| `backend/bebcare/services/stripe_billing_service.py` | fulfill 设 expires_at |
| `backend/bebcare/schemas/image_credit.py` | 响应含 `expires_at` |
| `backend/bebcare/main.py` | 启动清零 + 注册 interval job |
| `backend/bebcare/scheduler/apscheduler_service.py`（或 main） | 注册 expire job |
| `frontend/src/i18n/locales/pages.ts` | 30 天有效文案 |
| `README.md` | SKU 与过期说明 |
| `backend/tests/unit/test_credit_grant_service.py` | 过期/FEFO/清零测试 |
| `backend/tests/unit/test_stripe_billing_service.py` | fulfill expires_at |

---

### Task 1: Migration + model `expires_at`

**Files:**
- Create: `backend/migrations/versions/027_grant_expires_at.py`
- Modify: `backend/bebcare/models/image_credit.py`

- [ ] **Step 1: Add migration**

```python
"""image_credit_grants.expires_at

Revision ID: 027_grant_expires_at
Revises: 026_stripe_checkout_sessions
Create Date: 2026-08-21
"""

from alembic import op
import sqlalchemy as sa

revision = "027_grant_expires_at"
down_revision = "026_stripe_checkout_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "image_credit_grants",
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_image_credit_grants_expires_at",
        "image_credit_grants",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_image_credit_grants_expires_at", table_name="image_credit_grants")
    op.drop_column("image_credit_grants", "expires_at")
```

- [ ] **Step 2: Add model column**

在 `ImageCreditGrant` 增加：`expires_at = Column(DateTime, nullable=True, index=True)`

- [ ] **Step 3: Commit**（若用户要求再提交）

---

### Task 2: Settings + grant service（过期过滤、FEFO、清零）

**Files:**
- Modify: `backend/bebcare/config/settings.py`
- Modify: `backend/bebcare/services/credit_grant_service.py`
- Modify: `backend/bebcare/schemas/image_credit.py`
- Test: `backend/tests/unit/test_credit_grant_service.py`

**Interfaces:**
- `create_grant(..., expires_at: Optional[datetime] = None)`
- `expire_due_grants(db: Session) -> int`
- `STATUS_EXPIRED = "expired"`
- Settings: `image_credit_stripe_expiry_days: int = 30`，`image_credit_expire_interval_minutes: int = 60`

- [ ] **Step 1: Write failing tests**

```python
from datetime import datetime, timedelta
from bebcare.services.credit_grant_service import expire_due_grants, STATUS_EXPIRED

def test_expired_grant_excluded_from_remaining(db_session, user_id):
    past = datetime.utcnow() - timedelta(days=1)
    create_grant(
        db_session, user_id=user_id, quantity=5, source="stripe", expires_at=past
    )
    db_session.flush()
    assert remaining_credits(db_session, user_id) == 0


def test_reserve_fefo_uses_earlier_expiry(db_session, user_id):
    soon = datetime.utcnow() + timedelta(days=1)
    later = datetime.utcnow() + timedelta(days=10)
    g_later = create_grant(
        db_session, user_id=user_id, quantity=1, source="stripe", expires_at=later
    )
    g_soon = create_grant(
        db_session, user_id=user_id, quantity=1, source="stripe", expires_at=soon
    )
    db_session.flush()
    tid = str(uuid.uuid4())
    db_session.add(
        GenerateTask(
            task_id=tid, status="PENDING", owner_user_id=user_id, workspace_id=None
        )
    )
    db_session.flush()
    res = reserve_one(db_session, user_id=user_id, generate_task_id=tid)
    assert res.grant_id == g_soon.id


def test_expire_due_grants_zeros_and_marks(db_session, user_id):
    past = datetime.utcnow() - timedelta(hours=1)
    g = create_grant(
        db_session, user_id=user_id, quantity=3, source="stripe", expires_at=past
    )
    db_session.flush()
    n = expire_due_grants(db_session)
    db_session.flush()
    assert n == 1
    db_session.refresh(g)
    assert g.remaining == 0
    assert g.status == STATUS_EXPIRED
    assert expire_due_grants(db_session) == 0
```

- [ ] **Step 2: Run tests — expect FAIL**

`cd backend && python -m pytest tests/unit/test_credit_grant_service.py -v`

- [ ] **Step 3: Implement**

`settings.py` 增加两字段。

`credit_grant_service.py`：
- `STATUS_EXPIRED = "expired"`
- `_not_expired` 过滤：`(expires_at.is_(None)) | (expires_at > datetime.utcnow())`
- `create_grant` 接受并写入 `expires_at`
- `remaining_credits` / `reserve_one` 应用过滤；`reserve_one` 排序用  
  `order_by(case((expires_at.is_(None), 1), else_=0), expires_at.asc(), created_at.asc())`
- `expire_due_grants` 按 spec 清零

`CreditGrantResponse` 增加 `expires_at: Optional[datetime] = None`

- [ ] **Step 4: Run tests — expect PASS**

---

### Task 3: Stripe fulfill 写入 expires_at

**Files:**
- Modify: `backend/bebcare/services/stripe_billing_service.py`
- Test: `backend/tests/unit/test_stripe_billing_service.py`

- [ ] **Step 1: 在现有 fulfill 测试中断言**

```python
assert grant.expires_at is not None
delta = grant.expires_at - datetime.utcnow()
assert timedelta(days=29) < delta < timedelta(days=31)
```

- [ ] **Step 2: fulfill 调用**

```python
from datetime import timedelta
# ...
expires_at = datetime.utcnow() + timedelta(days=int(settings.image_credit_stripe_expiry_days))
grant = create_grant(..., expires_at=expires_at)
```

- [ ] **Step 3: 跑** `python -m pytest tests/unit/test_stripe_billing_service.py -v`

---

### Task 4: 启动时清零 + interval job

**Files:**
- Modify: `backend/bebcare/main.py`
- Modify: `backend/bebcare/scheduler/apscheduler_service.py`（增加 `register_credit_expiry_job` 或在 `start()` 内注册）

- [ ] **Step 1: startup 在 reclaim 之后调用 `expire_due_grants`**

- [ ] **Step 2: scheduler.start() 后注册**

```python
from apscheduler.triggers.interval import IntervalTrigger

def _run_expire_due_grants():
    from bebcare.database import SessionLocal
    from bebcare.services.credit_grant_service import expire_due_grants
    db = SessionLocal()
    try:
        n = expire_due_grants(db)
        db.commit()
        if n:
            logger.info("Expired %s image credit grant(s)", n)
    except Exception:
        db.rollback()
        logger.exception("expire_due_grants failed")
    finally:
        db.close()

# interval minutes from settings.image_credit_expire_interval_minutes
self.scheduler.add_job(
    _run_expire_due_grants,
    trigger=IntervalTrigger(minutes=minutes),
    id="expire_image_credit_grants",
    replace_existing=True,
    max_instances=1,
)
```

---

### Task 5: i18n + README + 本地 .env 提示

**Files:**
- Modify: `frontend/src/i18n/locales/pages.ts`（en + zh `subscribeCredits.packHint` / `body` 如需）
- Modify: `README.md`（SKU 表 + 30 天说明 + 示例 JSON）
- Modify: `backend/.env` **仅本地**：更新 `STRIPE_CREDIT_PACKS` credits/label；price_id 保留现有或占位，**不提交**

文案示例：
- EN: `Credits are valid for 30 days after purchase. Unused credits expire.`
- ZH: `购买后 30 天内有效，过期未用完作废。`

运营需在 Stripe 建 $3.99 / $9.99 / $19.99 三档并填入真实 `price_id`。

---

### Task 6: Sync + 全量相关测试

- [ ] `python scripts/sync_deploy_copies.py`
- [ ] `cd backend && python -m pytest tests/unit/test_credit_grant_service.py tests/unit/test_stripe_billing_service.py tests/unit/test_stripe_packs.py tests/api/test_billing_routes.py -v`

---

## Spec coverage

| Spec 项 | Task |
|---------|------|
| `expires_at` 列 | 1 |
| 懒排除 + FEFO + `expire_due_grants` | 2 |
| Stripe +30d | 3 |
| 定时 + startup | 4 |
| SKU 文案 / 文档 | 5 |
| hf-space 同步 | 6 |
