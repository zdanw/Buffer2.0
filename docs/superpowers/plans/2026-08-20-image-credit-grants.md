# 平台出图次数包（Credit Grants）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让用户用独立系统图像 Provider 出图并按 Credit Grant 次数包计费（试用 + admin 发放）；BYOK 不计次；预扣失败退回；Studio 显式选择平台额度 vs 我的供应商。

**Architecture:** 新表 `image_credit_grants` / `image_credit_reservations`；`CreditGrantService` 负责发放、FIFO 预扣、confirm/refund、过期 reserved 回收；`ImageProviderConfig.is_system` + 可空 `owner_user_id` 表示平台池；生成路由按 `image_provider_mode` 分支解析并预扣；任务终态驱动 confirm/refund。支付仅预留 `source`/`external_ref`。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、pytest、React、i18n。

**Spec:** [`docs/superpowers/specs/2026-08-20-image-credit-grants-design.md`](../specs/2026-08-20-image-credit-grants-design.md)

## Global Constraints

- 仅 **platform 出图**计次；`/generate/copywriting/` 与 BYOK 出图不碰 grant。
- 额度不足 HTTP **402**；系统 Provider 未配置 **503**；BYOK 未配置 **400**（现有文案）。
- 预扣：发起时 `reserved`；SUCCESS → `confirmed`；FAILED/取消 → `refunded` 并恢复 grant。
- Admin **无**隐式无限出图；需要额度则给自己发 grant。
- 调度与 Studio **共用** `CreditGrantService` / registry；platform 额度不足禁止静默改 BYOK。
- `hf-space/bebcare/` 与 `backend/bebcare/`、`hf-space/migrations/` 与 `backend/migrations/` 镜像同步（每个改 backend 的 task 同步对应 hf-space 文件）。
- 测试在 `backend/`：`python -m pytest tests/path -v`
- 首版不做：Stripe/微信 webhook、月卡、文案计费、用户自助收银台。

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/bebcare/config/settings.py` | `image_credit_signup_trial`、`image_credit_reserve_ttl_minutes` |
| `backend/bebcare/models/image_provider.py` | `is_system`；覆盖 `owner_user_id` 可空 |
| `backend/bebcare/models/image_credit.py` | `ImageCreditGrant`、`ImageCreditReservation` |
| `backend/bebcare/models/task.py` | `ScheduledTask.image_provider_mode` |
| `backend/bebcare/models/__init__.py` | 导出新模型 |
| `backend/migrations/versions/025_image_credit_grants.py` | 列/表/回填试用/RLS 清单 |
| `backend/bebcare/db/rls_tables.py` | 注册新表名 |
| `backend/bebcare/services/credit_grant_service.py` | 发放/余额/预扣/确认/退回/回收/试用 |
| `backend/bebcare/providers/registry.py` | `resolve_system_image_provider` |
| `backend/bebcare/schemas/generate.py` / `task.py` / `auth.py` / `image_credit.py` | 请求/响应字段 |
| `backend/bebcare/api/generate_routes.py` | mode 门禁 + 预扣 |
| `backend/bebcare/services/generate_task_store.py` | SUCCESS/FAILED 时 confirm/refund |
| `backend/bebcare/generator/content_generator.py` | platform 走 system resolve |
| `backend/bebcare/api/auth_routes.py` | 注册发试用；`/me` 返回额度 |
| `backend/bebcare/api/credit_grant_routes.py` | admin 发放/列表/revoke |
| `backend/bebcare/api/image_provider_routes.py` | list 排除 system；`_to_response` 真值 |
| `backend/bebcare/api/system_image_provider_routes.py` | admin CRUD 系统 Provider |
| `backend/bebcare/scheduler/apscheduler_service.py` | 传 mode + 预扣 |
| `backend/bebcare/api/task_routes.py` | 保存 `image_provider_mode` |
| `backend/bebcare/main.py` | 挂载新路由 |
| `frontend/src/api/generate.ts` / `auth.ts` / `imageProviders.ts` / `credits.ts` | API |
| `frontend/src/components/ImageModelPicker.tsx` | 来源二选一 |
| `frontend/src/pages/Studio.tsx` / `TaskConfiguration.tsx` | 传 mode |
| `frontend/src/pages/UserManagement.tsx` | 发放次数 |
| `frontend/src/pages/SystemImageProviderSettings.tsx` | admin 平台供应商 |
| `frontend/src/App.tsx` / `Sidebar.tsx` | 路由与入口 |
| `frontend/src/i18n/locales/*` | 文案 |
| `hf-space/...` | 与 backend 镜像 |

---

### Task 1: Settings + models + migration + RLS

**Files:**
- Modify: `backend/bebcare/config/settings.py`
- Modify: `backend/bebcare/models/image_provider.py`
- Create: `backend/bebcare/models/image_credit.py`
- Modify: `backend/bebcare/models/task.py`
- Modify: `backend/bebcare/models/__init__.py`
- Modify: `backend/bebcare/db/rls_tables.py`
- Create: `backend/migrations/versions/025_image_credit_grants.py`
- Mirror: `hf-space/` 对应文件
- Test: `backend/tests/unit/test_image_credit_models_migration.py`（或并入现有 rls 测试扩展）

**Interfaces:**
- Consumes: `OwnedMixin`、`APP_RLS_TABLES`、Alembic `024_prompt_dimension_owner`
- Produces:
  - Settings: `image_credit_signup_trial: int = 2`，`image_credit_reserve_ttl_minutes: int = 15`（env: `IMAGE_CREDIT_SIGNUP_TRIAL`、`IMAGE_CREDIT_RESERVE_TTL_MINUTES`）
  - `ImageProviderConfig.is_system: bool`（default False）；**覆盖** `owner_user_id` 为 `nullable=True`（系统行可为 NULL；非系统行应用层强制非空）
  - `ImageCreditGrant` / `ImageCreditReservation` 字段与 spec §1 一致
  - `ScheduledTask.image_provider_mode: str | None`（`'platform' | 'byok'`）
  - RLS 清单加入 `image_credit_grants`、`image_credit_reservations`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_rls_tables.py 追加（或新建 test_image_credit_schema.py）
from bebcare.db.rls_tables import APP_RLS_TABLES

def test_credit_tables_in_rls_list():
    assert "image_credit_grants" in APP_RLS_TABLES
    assert "image_credit_reservations" in APP_RLS_TABLES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_rls_tables.py::test_credit_tables_in_rls_list -v`  
Expected: FAIL（名称未在元组中）

- [ ] **Step 3: Implement models + settings + migration**

`image_credit.py` 核心：

```python
class ImageCreditGrant(Base):
    __tablename__ = "image_credit_grants"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String(32), nullable=False)  # signup_trial | admin_grant | stripe | wechat
    quantity = Column(Integer, nullable=False)
    remaining = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="active")  # active|exhausted|revoked
    note = Column(Text, nullable=True)
    external_ref = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ImageCreditReservation(Base):
    __tablename__ = "image_credit_reservations"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    generate_task_id = Column(String(36), ForeignKey("generate_tasks.task_id", ondelete="CASCADE"), nullable=False, unique=True)
    grant_id = Column(String(36), ForeignKey("image_credit_grants.id"), nullable=False)
    amount = Column(Integer, nullable=False, default=1)
    status = Column(String(16), nullable=False, default="reserved")  # reserved|confirmed|refunded
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

Migration `025_image_credit_grants.py`：

1. `image_provider_configs` 加 `is_system`（server_default false）；`owner_user_id` alter nullable  
2. 建两张新表；对 `user_id + source='signup_trial'` 建 **unique partial**（Postgres）或应用层幂等（SQLite 用 unique 索引 `uq_signup_trial_per_user` 在 `(user_id, source)` where source 仅 trial——若 SQLite 不支持 partial，则用 `(user_id, source)` 唯一且约定 trial 的 source 恒为 `signup_trial`）  
3. `scheduled_tasks.image_provider_mode` String(16) nullable  
4. 回填：对尚无任何 grant 的 user 插入 `signup_trial`（quantity/remaining = 2 或读不到 settings 时写死 2）  
5. 新表加入后续 RLS：因 `023` 已跑过，本迁移对两张新表直接 `ENABLE ROW LEVEL SECURITY`（与 `023` 同风格，无策略）

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_rls_tables.py::test_credit_tables_in_rls_list -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/bebcare/config/settings.py backend/bebcare/models/ backend/bebcare/db/rls_tables.py backend/migrations/versions/025_image_credit_grants.py hf-space/
git commit -m "feat(credits): add grant/reservation schema and system provider flag"
```

---

### Task 2: CreditGrantService

**Files:**
- Create: `backend/bebcare/services/credit_grant_service.py`
- Create: `backend/tests/unit/test_credit_grant_service.py`
- Mirror: `hf-space/bebcare/services/credit_grant_service.py`

**Interfaces:**
- Consumes: `ImageCreditGrant`、`ImageCreditReservation`、`settings.image_credit_signup_trial`
- Produces:
  - `class CreditError(Exception)` + subclasses 或 `code` 属性：`insufficient` | `not_found`
  - `def remaining_credits(db, user_id: str) -> int`
  - `def create_grant(db, *, user_id, quantity: int, source: str, note=None, external_ref=None) -> ImageCreditGrant`
  - `def ensure_signup_trial(db, user_id: str) -> ImageCreditGrant | None` — 若已有 `signup_trial` 则返回已有/None，不重复发
  - `def reserve_one(db, *, user_id, generate_task_id: str) -> ImageCreditReservation` — FIFO `FOR UPDATE`；不足 raise
  - `def confirm_reservation(db, generate_task_id: str) -> None`
  - `def refund_reservation(db, generate_task_id: str) -> None` — idempotent
  - `def revoke_grant(db, grant_id: str) -> ImageCreditGrant` — remaining→0, status=revoked；不影响已 reserved
  - `def reclaim_stale_reservations(db, *, older_than_minutes: int | None = None) -> int` — 超时 reserved 且任务非 PENDING/PROGRESS → refund；返回回收条数

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/unit/test_credit_grant_service.py
import pytest
from bebcare.services.credit_grant_service import (
    create_grant,
    remaining_credits,
    reserve_one,
    confirm_reservation,
    refund_reservation,
    ensure_signup_trial,
    CreditError,
)

def test_create_and_remaining(db_session, user_id):
    create_grant(db_session, user_id=user_id, quantity=5, source="admin_grant")
    assert remaining_credits(db_session, user_id) == 5

def test_reserve_confirm(db_session, user_id, generate_task_id):
    create_grant(db_session, user_id=user_id, quantity=1, source="admin_grant")
    reserve_one(db_session, user_id=user_id, generate_task_id=generate_task_id)
    assert remaining_credits(db_session, user_id) == 0
    confirm_reservation(db_session, generate_task_id)
    assert remaining_credits(db_session, user_id) == 0

def test_reserve_refund_restores(db_session, user_id, generate_task_id):
    create_grant(db_session, user_id=user_id, quantity=1, source="admin_grant")
    reserve_one(db_session, user_id=user_id, generate_task_id=generate_task_id)
    refund_reservation(db_session, generate_task_id)
    assert remaining_credits(db_session, user_id) == 1

def test_reserve_insufficient(db_session, user_id, generate_task_id):
    with pytest.raises(CreditError):
        reserve_one(db_session, user_id=user_id, generate_task_id=generate_task_id)

def test_signup_trial_idempotent(db_session, user_id, monkeypatch):
    from bebcare.config import settings as s
    monkeypatch.setattr(s.settings, "image_credit_signup_trial", 2)
    ensure_signup_trial(db_session, user_id)
    ensure_signup_trial(db_session, user_id)
    assert remaining_credits(db_session, user_id) == 2
```

（`db_session` / `user_id` / `generate_task_id` fixture：复用 `tests/conftest.py` 模式；若无现成 session fixture，按 `test_ownership.py` 风格用内存 SQLite 建最小表。）

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_credit_grant_service.py -v`  
Expected: FAIL import / not found

- [ ] **Step 3: Implement service**

`reserve_one` 伪代码：

```python
grants = (
    db.query(ImageCreditGrant)
    .filter(
        ImageCreditGrant.user_id == user_id,
        ImageCreditGrant.status == "active",
        ImageCreditGrant.remaining > 0,
    )
    .order_by(ImageCreditGrant.created_at.asc())
    .with_for_update()
    .all()
)
if not grants:
    raise CreditError("insufficient")
grant = grants[0]
grant.remaining -= 1
if grant.remaining == 0:
    grant.status = "exhausted"
res = ImageCreditReservation(...)
db.add(res)
db.flush()
return res
```

SQLite 测试环境：`with_for_update()` 可忽略；仍用条件更新兜底。  
`refund_reservation`：若 status 已是 refunded/confirmed 则 no-op（confirmed 不退）；refunded 时 `grant.remaining += amount`，若 status 曾为 exhausted 改回 active。

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_credit_grant_service.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/bebcare/services/credit_grant_service.py backend/tests/unit/test_credit_grant_service.py hf-space/bebcare/services/credit_grant_service.py
git commit -m "feat(credits): implement CreditGrantService reserve/confirm/refund"
```

---

### Task 3: Registry — resolve_system_image_provider

**Files:**
- Modify: `backend/bebcare/providers/registry.py`
- Modify: `backend/bebcare/providers/__init__.py`
- Create: `backend/tests/unit/test_resolve_system_provider.py`
- Mirror: hf-space 对应文件

**Interfaces:**
- Consumes: `ImageProviderConfig` where `is_system == True`
- Produces:
  - `SYSTEM_PROVIDER_UNAVAILABLE_MSG = "平台图像供应商未配置，请联系管理员。"`
  - `def resolve_system_image_provider(db: Session, image_model: Optional[str] = None) -> Tuple[object, Optional[str]]`
    - 查 `is_system==True && is_active==True`，优先 `is_default`，否则最新一条
    - 无则 `raise ValueError(SYSTEM_PROVIDER_UNAVAILABLE_MSG)`
  - 保留现有 `resolve_image_provider`（BYOK）；继续拒绝把字面 id `"system"` 当作用户 owned 配置（或改为：若传入真实 system 行 id 且 owner 不匹配仍 400——platform 路径不走此函数）

- [ ] **Step 1: Write the failing test**

```python
def test_resolve_system_missing(db_session):
    from bebcare.providers.registry import resolve_system_image_provider
    with pytest.raises(ValueError, match="平台图像供应商"):
        resolve_system_image_provider(db_session)

def test_resolve_system_ok(db_session, system_provider_row):
    from bebcare.providers.registry import resolve_system_image_provider
    provider, model = resolve_system_image_provider(db_session, None)
    assert model == system_provider_row.default_model
```

- [ ] **Step 2: Run to verify fail** → implement → **Step 3: Run to verify pass**

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(providers): resolve system image provider from is_system configs"
```

---

### Task 4: Generate routes + task store confirm/refund + ContentGenerator mode

**Files:**
- Modify: `backend/bebcare/schemas/generate.py`
- Modify: `backend/bebcare/api/generate_routes.py`
- Modify: `backend/bebcare/services/generate_task_store.py`
- Modify: `backend/bebcare/generator/content_generator.py`
- Create: `backend/tests/api/test_generate_credits.py`
- Mirror: hf-space 对应文件

**Interfaces:**
- Consumes: `reserve_one` / `confirm_reservation` / `refund_reservation` / `resolve_system_image_provider` / `resolve_image_provider`
- Produces:
  - `GenerateRequest.image_provider_mode: Optional[Literal["platform","byok"]] = None`
  - `_resolve_mode(db, user, request) -> str`：未传时有 BYOK→`byok`；else remaining>0→`platform`；else 400
  - `_owned_generate_product`：仅 `byok` 时 `assert_owned_ref` 图像供应商
  - `_require_image_provider`：按 mode 分支；platform 不足 → HTTP 402；system 缺失 → 503
  - 创建 task 后、投递 background **前**：若 platform 则 `reserve_one`；失败则删/标 FAILED task 并 402
  - `product_info["image_provider_mode"] = mode`；platform 时可不传用户 provider id
  - `update_generate_task`：当 status 变为 `SUCCESS` 调 `confirm_reservation`；`FAILED` 调 `refund_reservation`（同一 db session 内，注意 store 自开 Session——在 `update_generate_task` 内 import 并调用 service）
  - `ContentGenerator.generate_image_async`：若 `product_info.get("image_provider_mode")=="platform"` 或显式参数，调用 `resolve_system_image_provider`

- [ ] **Step 1: Write API tests**

```python
from unittest.mock import AsyncMock, patch

def test_platform_generate_requires_credits(client, user_headers, product_id):
    # fixture: user with 0 credits and no BYOK provider
    r = client.post("/v1/generate/image/", headers=user_headers, json={
        "product_id": product_id,
        "platform": "instagram",
        "image_provider_mode": "platform",
    })
    assert r.status_code == 402

@patch("bebcare.api.generate_routes.ContentGenerator.generate_image_async", new_callable=AsyncMock)
def test_platform_success_confirms_credit(mock_img, client, user_headers, product_id, system_provider, trial_user):
    mock_img.return_value = {"image_urls": ["https://example.com/a.png"], "dimensions": None, "image_prompt": None}
    before = remaining_via_me(client, user_headers)
    r = client.post("/v1/generate/image/", headers=user_headers, json={
        "product_id": product_id,
        "platform": "instagram",
        "image_provider_mode": "platform",
    })
    assert r.status_code == 200
    task_id = r.json()["task_id"]
    # poll or run background eagerly in test app
    wait_task_success(client, user_headers, task_id)
    assert remaining_via_me(client, user_headers) == before - 1

@patch("bebcare.api.generate_routes.ContentGenerator.generate_image_async", new_callable=AsyncMock)
def test_byok_does_not_consume(mock_img, client, user_headers, product_id, byok_provider):
    mock_img.return_value = {"image_urls": ["https://example.com/a.png"], "dimensions": None, "image_prompt": None}
    # ensure user has trial remaining > 0
    before = remaining_via_me(client, user_headers)
    r = client.post("/v1/generate/image/", headers=user_headers, json={
        "product_id": product_id,
        "platform": "instagram",
        "image_provider_mode": "byok",
        "image_provider_id": byok_provider["id"],
        "image_model": byok_provider["default_model"],
    })
    assert r.status_code == 200
    wait_task_success(client, user_headers, r.json()["task_id"])
    assert remaining_via_me(client, user_headers) == before

def test_copywriting_creates_no_reservation(client, user_headers, product_id, db_session):
    with patch("bebcare.api.generate_routes.ContentGenerator.generate_copywriting_async", new_callable=AsyncMock) as mock_cw:
        mock_cw.return_value = "hello"
        r = client.post("/v1/generate/copywriting/", headers=user_headers, json={
            "product_id": product_id,
            "platform": "instagram",
        })
        assert r.status_code == 200
    from bebcare.models.image_credit import ImageCreditReservation
    assert db_session.query(ImageCreditReservation).count() == 0
```

辅助函数 `remaining_via_me` / `wait_task_success` 写在同一测试文件顶部；若 BackgroundTasks 在 TestClient 内同步执行，则 POST 返回后直接查 status。

- [ ] **Step 2–4:** 红 → 实现 → 绿

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(generate): gate platform image gen with credit reserve/confirm"
```

---

### Task 5: Auth `/me` + signup trial + admin credit APIs

**Files:**
- Modify: `backend/bebcare/schemas/auth.py`
- Create: `backend/bebcare/schemas/image_credit.py`
- Modify: `backend/bebcare/api/auth_routes.py`
- Create: `backend/bebcare/api/credit_grant_routes.py`
- Modify: `backend/bebcare/main.py`
- Create: `backend/tests/api/test_credit_grant_admin.py`
- Mirror: hf-space

**Interfaces:**
- Consumes: `ensure_signup_trial`、`create_grant`、`remaining_credits`、`revoke_grant`、`get_current_admin_user`
- Produces:
  - `UserResponse` 增加：
    - `image_credits_remaining: int`
    - `has_system_image_provider: bool`
  - `register_user` / `create_user`（admin 建号）在 commit 用户后调用 `ensure_signup_trial`
  - Admin routes（prefix `/admin/users` 或挂在 auth 下，与现有 `/auth/users` 风格一致亦可：`/auth/users/{user_id}/credit-grants`）  
    - `GET .../credit-grants` → list  
    - `POST .../credit-grants` body `{quantity: int, note?: str}` → `create_grant(..., source="admin_grant")`  
    - `POST .../credit-grants/{grant_id}/revoke` → `revoke_grant`  
  - 非 admin → 403

- [ ] **Step 1: Tests**

```python
def test_register_gets_trial(client, monkeypatch):
    ...
    me = client.get("/v1/auth/me", headers=...).json()
    assert me["image_credits_remaining"] == 2

def test_non_admin_cannot_grant(client, user_headers, other_user_id):
    r = client.post(f"/v1/auth/users/{other_user_id}/credit-grants", headers=user_headers, json={"quantity": 10})
    assert r.status_code == 403

def test_admin_grant_increases_remaining(client, auth_headers, user_id):
    r = client.post(f"/v1/auth/users/{user_id}/credit-grants", headers=auth_headers, json={"quantity": 20, "note": "pack"})
    assert r.status_code == 200
    assert r.json()["remaining"] == 20
```

- [ ] **Step 2–4:** 红 → 实现（含 `has_system_image_provider` 查询）→ 绿

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(credits): expose remaining on /me and admin grant APIs"
```

---

### Task 6: System image provider admin API + user list exclusion

**Files:**
- Create: `backend/bebcare/api/system_image_provider_routes.py`
- Modify: `backend/bebcare/api/image_provider_routes.py`（`_to_response` 读真实 `is_system`；create 强制 `is_system=False`；list 已 owned 自然不含 NULL owner system 行——再显式 `.filter(is_system.is_(False))`）
- Modify: `backend/bebcare/main.py`
- Create: `backend/tests/api/test_system_image_provider.py`
- Mirror: hf-space

**Interfaces:**
- Consumes: 现有 ImageProvider create/update schema（可复用）、`get_current_admin_user`、`encrypt_secret`
- Produces:
  - `GET/POST /v1/admin/system-image-providers/`
  - `GET/PUT/DELETE /v1/admin/system-image-providers/{id}`
  - `POST .../{id}/set-default`、`.../test`、`.../models`（按需复用用户路由逻辑，但查 `is_system==True`）
  - 创建时：`is_system=True`，`owner_user_id=None`
  - 普通用户 GET `/image-providers/` 永不返回 system 行
  - 只读公开：`GET /v1/image-providers/system/summary`（需登录）返回 `{id, name, default_model, manual_models, has_provider: bool}` **不含 api key**——供 Studio platform 模式选模型

- [ ] **Step 1: Tests** — 非 admin 403；admin CRUD；user list 不含 system；summary 无 key

- [ ] **Step 2–4:** 实现 → 绿

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(providers): admin CRUD for system image provider"
```

---

### Task 7: Scheduler + task schema mode + stale reclaim

**Files:**
- Modify: `backend/bebcare/schemas/task.py`
- Modify: `backend/bebcare/api/task_routes.py`
- Modify: `backend/bebcare/scheduler/apscheduler_service.py`
- Modify: `backend/bebcare/main.py` 或 startup（调用 reclaim）
- Modify: `backend/tests/unit/test_scheduler_owner_scope.py` 或新建 `test_scheduler_credits.py`
- Mirror: hf-space

**Interfaces:**
- Consumes: Task 2–4 服务
- Produces:
  - Task create/update 接受 `image_provider_mode`
  - 调度执行：与 generate 相同解析；platform 则创建 GenerateTask（若调度也写 generate_tasks）或专用 execution id——**若调度不创建 GenerateTask**，则 `reserve_one` 的 `generate_task_id` 改用 `task_execution` id，或先创建 GenerateTask 再预扣（实现时与现网调度写库方式对齐；禁止第二套扣次逻辑）
  - 额度不足：记失败日志/execution failed，不改 mode
  - App 启动（`main.py` lifespan 或 scheduler 启动钩子）调用 `reclaim_stale_reservations`；可选每 N 分钟再跑

- [ ] **Step 1: Unit test** — mock remaining=0 + mode=platform → execution fails；mode=byok 不调用 reserve

- [ ] **Step 2–4:** 实现 → 绿

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(scheduler): honor image_provider_mode and credit reserve"
```

---

### Task 8: Frontend — credits API + ImageModelPicker + Studio/Tasks

**Files:**
- Modify: `frontend/src/api/auth.ts`（User 类型加 `image_credits_remaining`、`has_system_image_provider`）
- Modify: `frontend/src/api/generate.ts`（`image_provider_mode`）
- Create: `frontend/src/api/systemImageProvider.ts`（summary + admin CRUD）
- Create: `frontend/src/api/credits.ts`（admin grant helpers）
- Modify: `frontend/src/components/ImageModelPicker.tsx`
- Modify: `frontend/src/pages/Studio.tsx`
- Modify: `frontend/src/pages/TaskConfiguration.tsx`（及 `CreatePanel.tsx` 若传 selection）
- Modify: `frontend/src/i18n/locales/pages.ts` / `zh.base.ts` / `en.base.ts`

**Interfaces:**
- Consumes: `/auth/me`、`/image-providers/system/summary`
- Produces:
  - `ImageModelSelection` 增加 `image_provider_mode?: 'platform' | 'byok'`
  - Picker UI：来源单选；platform 用 summary 的 models；三态黄条；扣次提示
  - 默认：`has_system && remaining>0` → platform；else byok
  - Studio/Task 提交带 `image_provider_mode`；402/503 Toast + CTA（联系管理员 / 去图像模型）

- [ ] **Step 1:** 扩展 types 与 i18n keys（先写键名，组件引用）

Keys（示例）：
- `imageModelPicker.sourcePlatform` / `sourceByok`
- `imageModelPicker.creditsRemaining`
- `imageModelPicker.willConsumeOne`
- `imageModelPicker.creditsExhausted`
- `imageModelPicker.systemUnavailable`

- [ ] **Step 2:** 实现 Picker 来源切换与 Studio 传参

- [ ] **Step 3:** 手动验收清单（无 E2E 时）  
  - 有额度无 BYOK：可选平台并提交  
  - 额度 0 无 BYOK：平台 disabled + 黄条  
  - 仅 BYOK：可不花额度出图  

- [ ] **Step 4: Commit**

```bash
git commit -m "feat(studio): platform vs BYOK picker with credit awareness"
```

---

### Task 9: Frontend — Admin 系统 Provider 页 + 用户发放次数

**Files:**
- Create: `frontend/src/pages/SystemImageProviderSettings.tsx`（复用 `ImageProviderSettings` 表单模式，调 admin API）
- Modify: `frontend/src/pages/UserManagement.tsx` — 每行显示 remaining；「发放次数」对话框
- Modify: `frontend/src/App.tsx`、`Sidebar.tsx` — admin 入口「平台图像」
- Modify: i18n
- Optional: `ImageProviderSettings.tsx` 加一句「也可在 Studio 使用平台额度」

- [ ] **Step 1:** Admin 可保存系统 Provider（无 Key 不落用户列表）

- [ ] **Step 2:** Admin 给用户发 20 次后，该用户 `/me` / Studio 显示剩余增加

- [ ] **Step 3: Commit**

```bash
git commit -m "feat(admin): system image provider settings and credit grants UI"
```

---

### Task 10: Spec checklist verification + docs touch

**Files:**
- 对照 spec §4.6 十二条跑 pytest + 手工点验
- 若 README 有环境变量段：补充 `IMAGE_CREDIT_SIGNUP_TRIAL`、`IMAGE_CREDIT_RESERVE_TTL_MINUTES`

- [ ] **Step 1: Run full related tests**

```bash
cd backend
python -m pytest tests/unit/test_credit_grant_service.py tests/unit/test_resolve_system_provider.py tests/api/test_credit_grant_admin.py tests/api/test_system_image_provider.py tests/api/test_generate_credits.py -v
```

Expected: all PASS

- [ ] **Step 2: Manual / checklist map**

| Spec # | Covered by |
|--------|------------|
| 1 新注册 trial | Task 5 test |
| 2–3 platform success/fail | Task 4 |
| 4 remaining 0 | Task 4 |
| 5 BYOK | Task 4 |
| 6 并发 | Task 2 可加 `test_double_reserve_last_credit`（同 session 两次 reserve） |
| 7 admin 20 | Task 5 |
| 8 调度 | Task 7 |
| 9 非 admin 403 | Task 5 |
| 10 list 无 system | Task 6 |
| 11 copywriting | Task 4 断言无 reservation |
| 12 trial 幂等 | Task 2 |

若缺「并发」单测，在本 task 补进 `test_credit_grant_service.py` 后提交。

- [ ] **Step 3: Commit**

```bash
git commit -m "test(credits): cover spec checklist and document env vars"
```

---

## Self-review (plan vs spec)

| Spec 项 | Task |
|---------|------|
| Grant + Reservation 表、FIFO、signup_trial | 1–2 |
| is_system Provider、owner 可空 | 1, 6 |
| platform/byok mode、402/503/400 | 4 |
| 预扣 + SUCCESS/FAILED | 4 |
| 调度同逻辑 | 7 |
| `/me` remaining、admin 发放 | 5 |
| Studio 二选一 UI | 8 |
| Admin 系统 Provider + 发放 UI | 9 |
| 15min stale reclaim | 7 |
| 历史用户回填 trial | 1 migration |
| 支付预留 source/external_ref | 2 `create_grant` |
| hf-space 镜像 | Global + 各 task |
| 不做 Stripe/月卡/文案计费 | Global Constraints |

无 TBD/占位实现步骤；类型名在 Task 2/3/5 间一致（`remaining_credits`、`reserve_one`、`image_provider_mode`、`image_credits_remaining`）。
