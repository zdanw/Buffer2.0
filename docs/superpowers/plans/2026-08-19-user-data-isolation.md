# 用户数据隔离 + Supabase RLS 锁死 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每个登录用户只能读写自己的品牌/产品/任务/发布/生成记录与自备图像供应商、Buffer 账号；同时用 Alembic 对所有应用 `public` 表开启 RLS（无 anon 策略），堵住 Supabase Data API。

**Architecture:** 业务表增加必填 `owner_user_id` 与可空 `workspace_id`（第一期恒 `NULL`）。统一 `owned_query` / `get_owned_or_404` / `stamp_owner`；跨用户一律 404。后端 JWT 负责应用隔离；Postgres RLS 只锁死 PostgREST，后端 `DATABASE_URL` 高权限连接不受阻。凭证解析必须带 `owner_user_id`，禁止回落到全局默认或 `.env` 平台 Key。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、SQLite（测试/本地）、PostgreSQL/Supabase（生产）、pytest、React + i18n。

**Spec:** [`docs/superpowers/specs/2026-08-19-user-data-isolation-design.md`](../specs/2026-08-19-user-data-isolation-design.md)

## Global Constraints

- `owner_user_id` 必填（FK → `users.user_id`）；`workspace_id` 可空，创建时写 `NULL`；客户端不可设置这两列。
- 图像供应商 / Buffer **无**平台共享；每人自备；取消「仅管理员可写」。
- 跨用户资源与非法引用 → **404**；未配置 provider/buffer 却生成/发布 → **400**。
- RLS：所有应用 `public` 业务表 `ENABLE ROW LEVEL SECURITY`，**不** `CREATE POLICY`；SQLite 跳过；排除 `alembic_version`。
- 不做：workspaces 表、伪装登录、CDN 分目录、`auth.uid()` 行级策略、平台默认 Key。
- `hf-space/bebcare/` 与 `backend/bebcare/` 镜像文件必须同步改（生产 HF 走副本）。
- 测试命令在 `backend/` 下执行：`python -m pytest tests/path -v`

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/bebcare/models/ownership.py` | `OwnedMixin`（`owner_user_id`, `workspace_id`） |
| `backend/bebcare/services/ownership.py` | `owned_query` / `get_owned_or_404` / `stamp_owner` / `assert_owned_ref` |
| `backend/bebcare/db/rls_tables.py` | 应用表清单（迁移与测试共用） |
| `backend/migrations/versions/021_owner_workspace_columns.py` | 加可空列 |
| `backend/migrations/versions/022_owner_backfill_not_null.py` | 回填管理员 + NOT NULL + 索引/唯一约束 |
| `backend/migrations/versions/023_enable_rls.py` | Postgres ENABLE RLS |
| 各 `models/*.py` | 混入 mixin；`Brand.slug` 改为 `(owner_user_id, slug)` 唯一 |
| 各 `api/*_routes.py` | owned 过滤、创建盖章、引用校验 |
| `providers/registry.py` | `resolve_image_provider(..., owner_user_id=)`，禁止 env 静默回落 |
| `services/buffer_account_service.py` | 按 owner 解析，禁止 env 静默回落 |
| `services/generate_task_store.py` | 创建/读取带 owner |
| `scheduler/apscheduler_service.py` | 任务产品与凭证按任务 owner |
| `frontend/src/components/Sidebar.tsx`、`App.tsx` | 普通用户可见图像模型 / Buffer 设置 |
| `frontend/src/i18n/locales/*.ts` | 空状态文案（引导自配 Key） |

**不加 owner 的表（仍开 RLS）：** `users`、`product_images`（经 product）、`prompt_dimensions` / compat / policies（全局只读模板）、`product_dimensions`（经 product）、`operation_logs`。

---

### Task 1: 归属辅助函数

**Files:**
- Create: `backend/bebcare/services/ownership.py`
- Test: `backend/tests/unit/test_ownership.py`

**Interfaces:**
- Consumes: `User.user_id`；SQLAlchemy `Session` 与带 `owner_user_id` 的 Model
- Produces:
  - `owned_query(db: Session, model: type, user: User) -> Query`
  - `get_owned_or_404(db, model, ident, user, *, id_attr: str) -> Any`（找不到 → `HTTPException(404, "Not found")`）
  - `stamp_owner(obj: Any, user: User) -> None`（`owner_user_id=user.user_id`, `workspace_id=None`）
  - `assert_owned_ref(db, model, ident, user, *, id_attr: str) -> None`（`ident` 为 `None` 则 return；否则同 404）

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_ownership.py
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from bebcare.services.ownership import stamp_owner, get_owned_or_404, assert_owned_ref
from bebcare.models.user import User


def test_stamp_owner_sets_user_and_null_workspace():
    user = User(user_id="u-1")
    obj = MagicMock()
    stamp_owner(obj, user)
    assert obj.owner_user_id == "u-1"
    assert obj.workspace_id is None


def test_get_owned_or_404_raises_404_when_missing():
    db = MagicMock()
    db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
    user = User(user_id="u-1")
    with pytest.raises(HTTPException) as ei:
        get_owned_or_404(db, MagicMock(), "id-1", user, id_attr="brand_id")
    assert ei.value.status_code == 404


def test_assert_owned_ref_skips_none():
    assert_owned_ref(MagicMock(), MagicMock(), None, User(user_id="u-1"), id_attr="id")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_ownership.py -v`  
Expected: FAIL（模块不存在）

- [ ] **Step 3: Write minimal implementation**

```python
# backend/bebcare/services/ownership.py
from typing import Any, Optional, Type
from fastapi import HTTPException
from sqlalchemy.orm import Session, Query
from bebcare.models.user import User


def owned_query(db: Session, model: Type[Any], user: User) -> Query:
    return db.query(model).filter(model.owner_user_id == user.user_id)


def get_owned_or_404(
    db: Session,
    model: Type[Any],
    ident: str,
    user: User,
    *,
    id_attr: str,
) -> Any:
    row = (
        owned_query(db, model, user)
        .filter(getattr(model, id_attr) == ident)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return row


def stamp_owner(obj: Any, user: User) -> None:
    obj.owner_user_id = user.user_id
    obj.workspace_id = None


def assert_owned_ref(
    db: Session,
    model: Type[Any],
    ident: Optional[str],
    user: User,
    *,
    id_attr: str,
) -> None:
    if ident is None:
        return
    get_owned_or_404(db, model, ident, user, id_attr=id_attr)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_ownership.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/bebcare/services/ownership.py backend/tests/unit/test_ownership.py
git commit -m "feat: add owner-scoped query helpers for per-user isolation"
```

---

### Task 2: ORM mixin 与模型列

**Files:**
- Create: `backend/bebcare/models/ownership.py`
- Modify: `backend/bebcare/models/brand.py`、`product.py`（仅 `Product`）、`task.py`、`publish.py`、`generate_task.py`、`image_provider.py`、`buffer_account.py`
- Modify: `backend/bebcare/models/brand.py` — `slug` 去掉全局 `unique=True`，加 `__table_args__ = (UniqueConstraint("owner_user_id", "slug", name="uq_brands_owner_slug"),)`
- Modify: `backend/bebcare/models/product.py` — `brand_id` **不要**再 `default=GENERIC_BRAND_ID`（避免新产品挂到管理员的系统品牌）

**Interfaces:**
- Consumes: Task 1 的 stamp 字段名
- Produces: 下列模型均有 `owner_user_id: str`、`workspace_id: Optional[str]`：`Brand`, `Product`, `ScheduledTask`, `TaskExecution`, `ManualTaskDraft`, `PublishRecord`, `GenerateTask`, `ImageProviderConfig`, `BufferAccount`

```python
# backend/bebcare/models/ownership.py
from sqlalchemy import Column, String, ForeignKey

class OwnedMixin:
    owner_user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(String(36), nullable=True, index=True)
```

每个目标 class 改为 `class Brand(OwnedMixin, Base):`（**Mixin 在 Base 前**）。

`initialize_brands` / `upsert_brand_from_kit` 必须在插入前设置 `owner_user_id` 为当前库中最早的 `is_admin=True` 用户（与迁移回填同一规则）；否则 `create_all` 测试会因 NOT NULL 失败。

- [ ] **Step 1: 改模型与 brand seed**

修改 `backend/bebcare/services/brand_seed_service.py`：在 `upsert_brand_from_kit` / `initialize_brands` 中：

```python
admin = (
    db.query(User)
    .filter(User.is_admin.is_(True))
    .order_by(User.created_at.asc())
    .first()
)
if not admin:
    raise RuntimeError("Cannot seed brands without an admin user")
# 新建时 stamp；更新已有行时若 owner_user_id 为空也补上
```

（测试 `conftest` 先 `initialize_data()` 再 seed，admin 已存在。）

- [ ] **Step 2: Run existing tests**

Run: `python -m pytest tests/unit tests/api -q`  
Expected: 若 create_all 缺列导致失败则修模型；auth 测试仍 PASS。

- [ ] **Step 3: Commit**

```bash
git add backend/bebcare/models backend/bebcare/services/brand_seed_service.py
git commit -m "feat: add owner_user_id and workspace_id columns on tenant models"
```

---

### Task 3: Alembic 021/022 — 加列、回填、收紧

**Files:**
- Create: `backend/migrations/versions/021_owner_workspace_columns.py`
- Create: `backend/migrations/versions/022_owner_backfill_not_null.py`

**OWNER_TABLES**（021/022 共用，写在 021 顶部也可复制到 022）：

`brands`, `products`, `scheduled_tasks`, `task_executions`, `manual_task_drafts`, `publish_records`, `generate_tasks`, `image_provider_configs`, `buffer_accounts`

`down_revision`：`021` revises `020_buffer_account_unique`；`022` revises `021_owner_workspace`。

- [ ] **Step 1: 021 upgrade — 可空列**

对每张表（SQLite 用 `batch_alter_table`，与 `env.py` 的 `render_as_batch` 一致）：

```python
op.add_column("brands", sa.Column("owner_user_id", sa.String(36), nullable=True))
op.add_column("brands", sa.Column("workspace_id", sa.String(36), nullable=True))
```

（循环 OWNER_TABLES 重复。）

- [ ] **Step 2: 022 upgrade — 回填 + NOT NULL + FK/index**

```python
# 绑定连接执行
bind = op.get_bind()
admin_id = bind.execute(
    sa.text(
        "SELECT user_id FROM users WHERE is_admin = 1 OR is_admin = true "
        "ORDER BY created_at ASC LIMIT 1"
    )
).scalar()
# SQLite 布尔可能是 1；若无 admin：raise RuntimeError
for table in OWNER_TABLES:
    op.execute(
        sa.text(f"UPDATE {table} SET owner_user_id = :aid WHERE owner_user_id IS NULL")
        .bindparams(aid=admin_id)
    )
```

然后每表：`alter_column owner_user_id nullable=False`；`create_foreign_key` → `users.user_id` ON DELETE CASCADE；`create_index` `ix_<table>_owner_user_id`。

**brands：** `drop_index` / 去掉 slug 全局 unique（现有 `ix`/`unique` 名以 013 迁移为准，实现时 `inspect` 或读 `013_brands.py`），再：

```python
op.create_unique_constraint("uq_brands_owner_slug", "brands", ["owner_user_id", "slug"])
```

- [ ] **Step 3: 022 downgrade**

删约束/索引/FK，列改回可空，**不要**试图还原「全局共享」语义。021 downgrade 删两列。

- [ ] **Step 4: 本地校验**

Run: `cd backend && python -c "from bebcare.db.migrate import run_migrations"` 仅当有可迁移库时；SQLite 测试仍走 `create_all`。至少确认 revision 链：`021` → `022`，`down_revision` 无断裂。

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/versions/021_owner_workspace_columns.py backend/migrations/versions/022_owner_backfill_not_null.py
git commit -m "feat: migrate existing rows onto admin owner_user_id"
```

---

### Task 4: Alembic 023 — ENABLE RLS（Postgres only）

**Files:**
- Create: `backend/bebcare/db/rls_tables.py`
- Create: `backend/migrations/versions/023_enable_rls.py`
- Test: `backend/tests/unit/test_rls_tables.py`

**Interfaces:**
- Produces: `APP_RLS_TABLES: tuple[str, ...]` — 与 `Base.metadata.tables` 减去 `alembic_version` 一致

```python
# backend/bebcare/db/rls_tables.py
APP_RLS_TABLES = (
    "users",
    "products",
    "product_images",
    "scheduled_tasks",
    "task_executions",
    "manual_task_drafts",
    "publish_records",
    "operation_logs",
    "brands",
    "prompt_dimensions",
    "prompt_dimension_compatibilities",
    "prompt_dimension_compat_policies",
    "product_dimensions",
    "image_provider_configs",
    "generate_tasks",
    "buffer_accounts",
)
```

实现时用 `inspect(Base.metadata)` 核对，缺表补进 tuple。**禁止** `CREATE POLICY`。

- [ ] **Step 1: Failing test — 清单覆盖 metadata**

```python
# backend/tests/unit/test_rls_tables.py
from bebcare.database import Base
import bebcare.models  # noqa: F401
from bebcare.db.rls_tables import APP_RLS_TABLES

def test_rls_table_list_covers_orm_tables():
    orm = {t.name for t in Base.metadata.sorted_tables}
    assert set(APP_RLS_TABLES) == orm
```

- [ ] **Step 2: Run test**（先写空 tuple 应 FAIL，再填全量 PASS）

- [ ] **Step 3: 023 migration**

```python
revision = "023_enable_rls"
down_revision = "022_owner_backfill_not_null"

from bebcare.db.rls_tables import APP_RLS_TABLES

def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for name in APP_RLS_TABLES:
        op.execute(sa.text(f'ALTER TABLE "{name}" ENABLE ROW LEVEL SECURITY'))

def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for name in APP_RLS_TABLES:
        op.execute(sa.text(f'ALTER TABLE "{name}" DISABLE ROW LEVEL SECURITY'))
```

约定：以后新建表的迁移 **末尾** 对 Postgres `ENABLE ROW LEVEL SECURITY`，并追加 `APP_RLS_TABLES`。

- [ ] **Step 4: Commit**

```bash
git add backend/bebcare/db/rls_tables.py backend/migrations/versions/023_enable_rls.py backend/tests/unit/test_rls_tables.py
git commit -m "feat: enable Postgres RLS on app tables without public policies"
```

---

### Task 5: 隔离 API 测试夹具 + 核心用例（先红）

**Files:**
- Modify: `backend/tests/conftest.py` — 增加挂载 brands / products / image-providers / buffer-accounts 的 app（或新 fixture `full_client`）
- Create: `backend/tests/api/test_owner_isolation.py`

**Interfaces:**
- Consumes: 登录、管理员创建用户（已有 `/v1/auth/users`）
- Produces: 用户 A/B 的 header fixture；后续 Task 6–8 继续加断言到同一文件或按资源拆文件

- [ ] **Step 1: Fixture**

在 `conftest.py` 增加 `_build_full_test_app()`：与 `main.py` 相同 `include_router`（auth、brand、product、task、generate、publish、prompt_dimension、image_provider、buffer_account）。`full_client` session fixture。

辅助：

```python
def register_or_create_user(client, auth_headers, username, email, password):
    resp = client.post("/v1/auth/users", headers=auth_headers, json={
        "username": username, "email": email, "password": password, "is_admin": False,
    })
    assert resp.status_code == 201
    login = client.post("/v1/auth/login/", data={"username": username, "password": password})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}
```

- [ ] **Step 2: 先写失败用例（品牌）**

```python
def test_user_b_cannot_get_user_a_brand(full_client, auth_headers):
    headers_a = register_or_create_user(full_client, auth_headers, "iso_a", "iso_a@test.local", "PassA123!")
    headers_b = register_or_create_user(full_client, auth_headers, "iso_b", "iso_b@test.local", "PassB123!")
    created = full_client.post("/v1/brands/", headers=headers_a, json={"name": "Alpha Kit"})
    assert created.status_code in (200, 201)
    brand_id = created.json()["brand_id"]
    listed_b = full_client.get("/v1/brands/", headers=headers_b)
    assert listed_b.status_code == 200
    ids = [x["brand_id"] for x in listed_b.json()]
    assert brand_id not in ids
    got = full_client.get(f"/v1/brands/{brand_id}", headers=headers_b)
    assert got.status_code == 404
```

（按现有 `BrandCreate` schema 调整 JSON 字段；若 POST 路径无尾斜杠，与 OpenAPI 对齐。）

- [ ] **Step 3: Run** — Expected: FAIL（B 仍能看见 A 的品牌）

- [ ] **Step 4: Commit tests only（允许红）**

```bash
git add backend/tests/conftest.py backend/tests/api/test_owner_isolation.py
git commit -m "test: add cross-user brand isolation coverage"
```

若仓库 hook 禁止红测提交，则本 commit 与 Task 6 合并。

---

### Task 6: 品牌 / 产品路由隔离

**Files:**
- Modify: `backend/bebcare/api/brand_routes.py` — 列表/详情/改/删用 `owned_query` / `get_owned_or_404`；创建 `stamp_owner`；`buffer_account_id` 经 `assert_owned_ref(..., BufferAccount, id_attr="id")`；删除品牌时把该用户名下产品的 `brand_id` 置 `NULL`（**不要**改成全局 `GENERIC_BRAND_ID`）
- Modify: `backend/bebcare/api/product_routes.py` — 同上；`brand_id` 必须属于当前用户
- Modify: `backend/bebcare/services/brand_context.py` — `get_brand_for_product` **禁止**回落到其他用户的 `is_generic` / `GENERIC_BRAND_ID`；仅用 `product.brand_id` 且品牌 `owner_user_id == product.owner_user_id`，否则 404/明确错误
- Test: 扩展 `test_owner_isolation.py`：产品跨用户 404；A 不能把产品挂到 B 的 `brand_id`

- [ ] **Step 1: 实现路由过滤**（每个 list 类似）

```python
def list_brands(..., current_user: User = Depends(get_current_active_user)):
    rows = owned_query(db, Brand, current_user).order_by(Brand.created_at.desc()).all()
```

创建：

```python
brand = Brand(...)
stamp_owner(brand, current_user)
```

- [ ] **Step 2: 跑隔离测试**

Run: `python -m pytest tests/api/test_owner_isolation.py -v`  
Expected: 品牌/产品相关 PASS

- [ ] **Step 3: Commit**

```bash
git add backend/bebcare/api/brand_routes.py backend/bebcare/api/product_routes.py backend/bebcare/services/brand_context.py backend/tests/api/test_owner_isolation.py
git commit -m "feat: scope brand and product APIs to the current user"
```

---

### Task 7: 任务 / 草稿 / 执行 / 发布 / 生成任务

**Files:**
- Modify: `backend/bebcare/api/task_routes.py`、`publish_routes.py`、`generate_routes.py`
- Modify: `backend/bebcare/services/generate_task_store.py`
  - `create_generate_task(task_id, status="PENDING", *, owner_user_id: str)`
  - `get_generate_task(task_id, *, owner_user_id: str) -> Optional[dict]`（owner 不匹配当 None → 路由 404）
- Test: A 创建的 generate status，B GET → 404；任务列表互不可见；创建任务时 `image_provider_id` / `target_products` 引用他人 → 404

`generate_routes.py`：`get_owned_or_404(..., Product, request.product_id, current_user, id_attr="product_id")`；校验 `image_provider_id`；`create_generate_task(..., owner_user_id=current_user.user_id)`。路由需注入 `current_user`（现依赖挂在 router 级，函数内再 `Depends(get_current_active_user)`）。

- [ ] **Step 1: 改 store 与 generate/task/publish 查询**
- [ ] **Step 2: 补测试并跑** `python -m pytest tests/api/test_owner_isolation.py tests/api/test_auth_and_generate.py -v`
- [ ] **Step 3: Commit**

```bash
git commit -m "feat: isolate tasks, publishes, and generate jobs by owner"
```

---

### Task 8: 图像供应商 / Buffer — 主人可写 + 按用户默认

**Files:**
- Modify: `backend/bebcare/api/image_provider_routes.py` — 写操作 `get_current_active_user` 替代 `get_current_admin_user`；list/get/update/delete/test 走 owned；`_clear_other_defaults` **必须** `filter(owner_user_id==current_user.user_id)`
- Modify: `backend/bebcare/api/buffer_account_routes.py` — 同样
- Modify: `backend/bebcare/providers/registry.py`

```python
def resolve_image_provider(
    db: Optional[Session] = None,
    image_provider_id: Optional[str] = None,
    image_model: Optional[str] = None,
    *,
    owner_user_id: Optional[str] = None,
) -> Tuple[object, Optional[str]]:
```

规则：

1. 查询始终 `ImageProviderConfig.owner_user_id == owner_user_id`（缺 owner_user_id 则 `ValueError`，由路由变成 400）。
2. **删除**「DB 全局 default → `.env` Doubao」静默回落。
3. `image_provider_id == "system"`：视为未找到（404/400），不再注入平台 Key。
4. 用户无配置 / id 不属于自己 → `ValueError`，API **400**，detail 提示去设置页配置供应商。
5. list 接口**不要**再 prepend `_system_provider_response()`。

- Modify: `backend/bebcare/services/buffer_account_service.py` — `resolve_buffer_api_token(..., owner_user_id: str)`：绑定品牌的 Buffer 必须 `account.owner_user_id == owner_user_id`；默认账号仅在**同一 owner** 内；**禁止**回落到 `settings.buffer_api_token` 作为跨用户默认（无账号 → `None`，发布路径 400）。
- Modify: `content_generator.py` 调用处传入 `owner_user_id`（从 product_info 或 session 产品行读取）。
- Test: 非管理员 POST `/image-providers/` 201；B 不能 GET/DELETE A 的 provider；A 不能用 B 的 provider id 生成。

- [ ] **Step 1: 实现 + 测试**
- [ ] **Step 2: Run** `python -m pytest tests/api/test_owner_isolation.py tests/unit -q`
- [ ] **Step 3: Commit**

```bash
git commit -m "feat: let each user manage their own image providers and Buffer accounts"
```

---

### Task 9: 调度器与凭证执行路径

**Files:**
- Modify: `backend/bebcare/scheduler/apscheduler_service.py`
  - 加载任务：保持 `enabled==True`（全表），但选产品时 `Product.owner_user_id == task.owner_user_id`
  - `resolve_image_provider(..., owner_user_id=task.owner_user_id)`
  - `resolve_buffer_api_token(..., owner_user_id=task.owner_user_id)`
- Modify: `backend/bebcare/generator/content_generator.py` 中 `resolve_image_provider` 调用，传入 product/task owner
- Test: `backend/tests/unit/test_scheduler_owner_scope.py` — mock session：task owner A，库中有 B 的产品，选品结果不含 B

```python
def test_scheduler_products_match_task_owner():
    # 用 MagicMock query 链或 sqlite 插两条 Product + 一条 ScheduledTask
    ...
```

若 scheduler 函数难测，抽 `def products_for_task(session, task) -> list[Product]` 再测该函数。

- [ ] **Step 1: 抽出选品函数并写测试**
- [ ] **Step 2: 接入 apscheduler 与 content_generator**
- [ ] **Step 3: Commit**

```bash
git commit -m "feat: run scheduled jobs with the task owner's credentials only"
```

---

### Task 10: Prompt 维度绑定随产品；管理员边界

**Files:**
- Modify: `backend/bebcare/api/prompt_dimension_routes.py` — 全局 `prompt_dimensions` 仍全员可读；写操作可保持 admin（系统模板）。`ProductDimension` 读写前 `get_owned_or_404` 对应 `Product`。
- Modify: `backend/bebcare/api/brand_routes.py` — `initialize_brand_pack` 改为品牌主人可调（不必 admin），内部仍只改该品牌。
- 确认 `/v1/auth/users` 仍 `get_current_admin_user`。
- Test: 管理员登录 **list brands** 不含用户 B 创建的品牌；admin 用户 CRUD 仍 201。

- [ ] **Step 1: 实现与测试**
- [ ] **Step 2: Commit**

```bash
git commit -m "feat: keep prompt templates global while product bindings stay owned"
```

---

### Task 11: 前端导航、空状态、文案

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx` — `image-models` 与 `buffer-accounts` 放入所有登录用户可见的 settings 组；`users` 仍仅 `isAdmin`
- Modify: `frontend/src/App.tsx` — 去掉「仅 admin 才 mount ImageProviderSettings / BufferAccountSettings」
- Modify: `frontend/src/i18n/locales/en.base.ts`、`zh.base.ts`、`pages.ts`（及 placeholders 若有）
  - `imageProviders.emptyState`：改为引导「添加你自己的 API Key」，删除「系统默认 Seedream 仍可用」
  - `pages.ts` 中 `emptyUsesDefault`：改为「留空则使用你的默认供应商」，禁止提 env Doubao
  - 品牌空状态：引导创建自己的品牌套件（新用户看不到管理员种子品牌）

- [ ] **Step 1: 改导航与 i18n**
- [ ] **Step 2: 手动核对** 非 admin 侧栏出现图像模型与 Buffer；用户管理仍隐藏
- [ ] **Step 3: Commit**

```bash
git commit -m "feat: let every user open provider and Buffer settings"
```

---

### Task 12: 同步 hf-space 副本并跑全量测试

**Files:** 与 backend 对应的 `hf-space/bebcare/models/*`、`services/ownership.py`、`services/brand_seed_service.py`、`services/brand_context.py`、`services/buffer_account_service.py`、`services/generate_task_store.py`、`api/*_routes.py`、`providers/registry.py`、`scheduler/apscheduler_service.py`、`generator/content_generator.py`、`db/rls_tables.py`  
HF 若**不**自带 `migrations/`，依赖与 backend 同一 Supabase，**只同步运行时代码**；Alembic 仍只放 `backend/migrations/`。

- [ ] **Step 1: 将 Task 1–10 的运行时改动镜像到 hf-space（禁止只改一边）**
- [ ] **Step 2: 全量测试**

Run: `python -m pytest tests -q`（在 `backend/`）  
Expected: PASS；无新增失败

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: mirror per-user isolation into the Hugging Face Space copy"
```

---

## 上线核对（非代码任务，实现后执行）

1. 备份 Supabase。
2. 部署使 `auto_migrate` 跑到 `023_enable_rls`。
3. Advisors：`rls_disabled_in_public` 应消失。
4. 用 anon key 请求 REST ` /rest/v1/users` 应被拒。
5. 管理员账号原数据仍在；新注册用户品牌/供应商列表为空。
6. 管理员不可在 UI 看到他人品牌。

---

## Self-review（对照 spec）

| Spec 项 | Task |
|---------|------|
| owner_user_id + workspace_id | 2, 3 |
| 存量归管理员 | 3 |
| 无平台共享 Key/Buffer | 8, 9, 11 |
| API 404 / 盖章 / 引用 | 5–8 |
| 管理员严格隔离 | 6, 10 |
| 异步/定时用任务 owner 凭证 | 7, 9 |
| RLS Alembic 无 policy | 4 |
| SQLite 跳过 RLS | 4 |
| 前端主人可配供应商 | 11 |
| product_images 不冗余 owner | 2（未加列） |
| 不做 workspace/伪装/CDN | 全计划未包含 |
| hf-space 同步 | 12 |
