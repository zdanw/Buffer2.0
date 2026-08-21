# Stripe 沙盒次数包 Checkout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Stripe 测试模式下用 Hosted Checkout 购买平台出图次数包；支付成功经 webhook 自动 `create_grant(source=stripe)`，并用 `stripe_checkout_sessions` 表做状态与幂等。

**Architecture:** 环境变量配置允许的 `price_id`→`credits`；登录用户创建 Checkout Session（先落本地 pending 行）；Stripe `checkout.session.completed` 验签后标 paid 并发放 grant；前端购买弹窗改为选包跳转，移除联系管理员入口。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、`stripe` Python SDK、pytest（mock Stripe）、React、i18n。

**Spec:** [`docs/superpowers/specs/2026-08-21-stripe-credit-checkout-design.md`](../specs/2026-08-21-stripe-credit-checkout-design.md)

## Global Constraints

- 仅 **一次性次数包**；不做订阅 / 退款扣回 / Customer Portal / 微信。
- SKU **不硬编码**：价格与档位只来自 Stripe Dashboard + `STRIPE_CREDIT_PACKS`。
- 无 `STRIPE_SECRET_KEY` 或 packs 为空 → billing **关闭**（`enabled=false`，checkout 返回 **503**）。
- Webhook **必须**验签；用原始 request body，禁止先 `await request.json()` 再验签。
- Grant 发放只走 `credit_grant_service.create_grant`；`source="stripe"`，`external_ref=stripe_session_id`。
- 幂等：会话已 `paid` 或已存在同 `external_ref` 的 stripe grant → webhook 仍返回 200，不重复加次数。
- `hf-space/` / `space4/` 与 `backend/` 镜像：改 backend 后跑 `python scripts/sync_deploy_copies.py`（或按 task 同步对应文件）。
- 测试在 `backend/`：`python -m pytest tests/path -v`
- 前端购买入口只走 Stripe；**移除**联系管理员 CTA（admin 发放 API 可保留）。

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/requirements.txt` | 增加 `stripe` |
| `backend/bebcare/config/settings.py` | Stripe / packs / `frontend_base_url`；去掉对购买 UI 的 `billing_contact` 依赖（设置项可暂留以免破坏旧 env） |
| `backend/bebcare/billing/packs.py` | 解析 `STRIPE_CREDIT_PACKS` JSON |
| `backend/bebcare/models/stripe_checkout.py` | `StripeCheckoutSession` |
| `backend/bebcare/models/__init__.py` | 导出模型 |
| `backend/bebcare/db/rls_tables.py` | 注册 `stripe_checkout_sessions` |
| `backend/migrations/versions/026_stripe_checkout_sessions.py` | 表 + stripe grant `external_ref` 唯一 |
| `backend/bebcare/services/credit_grant_service.py` | 增加 `SOURCE_STRIPE = "stripe"` |
| `backend/bebcare/services/stripe_billing_service.py` | 创建 Session、fulfill webhook |
| `backend/bebcare/schemas/billing.py` | 请求/响应 schema |
| `backend/bebcare/api/billing_routes.py` | packs / checkout / webhook |
| `backend/bebcare/main.py` | 挂载 billing 路由（webhook **不要**全局 JWT） |
| `backend/bebcare/api/auth_routes.py` / `schemas/auth.py` | `/me` 改为返回 `billing_enabled`；可停止依赖 `billing_contact` 展示 |
| `backend/.env.example` / `README.md` | 文档 |
| `frontend/src/api/billing.ts` | 客户端 API |
| `frontend/src/api/auth.ts` | `billing_enabled` |
| `frontend/src/components/SubscribeCreditsModal.tsx` | 选包 + Checkout |
| `frontend/src/components/ImageModelPicker.tsx` | 去掉 billingContact；传 enabled |
| `frontend/src/i18n/locales/pages.ts` | 文案 |
| `frontend/src/pages/Studio.tsx`（或 picker） | `?checkout=success` 刷新额度 |
| `backend/tests/...` | packs / service / API 测试 |

---

### Task 1: Stripe 依赖 + settings + packs 解析

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/bebcare/config/settings.py`
- Create: `backend/bebcare/billing/__init__.py`
- Create: `backend/bebcare/billing/packs.py`
- Test: `backend/tests/unit/test_stripe_packs.py`

**Interfaces:**
- Consumes: `pydantic_settings.BaseSettings`
- Produces:
  - Settings 字段：
    - `stripe_secret_key: str | None = None`（env `STRIPE_SECRET_KEY`）
    - `stripe_webhook_secret: str | None = None`（`STRIPE_WEBHOOK_SECRET`）
    - `stripe_credit_packs: str = "[]"`（`STRIPE_CREDIT_PACKS`，原始 JSON 字符串）
    - `frontend_base_url: str = "http://localhost:5174"`（`FRONTEND_BASE_URL`）
  - `CreditPack(TypedDict | dataclass)`: `price_id: str`, `credits: int`, `label: str`
  - `parse_credit_packs(raw: str) -> list[CreditPack]` — 非法 JSON / 缺字段 / `credits < 1` 抛 `ValueError`
  - `get_credit_packs() -> list[CreditPack]` — 读 settings 并 parse
  - `find_pack(price_id: str) -> CreditPack | None`
  - `is_billing_enabled() -> bool` — `bool(settings.stripe_secret_key) and len(get_credit_packs()) > 0`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_stripe_packs.py
import pytest
from bebcare.billing.packs import parse_credit_packs, is_billing_enabled


def test_parse_credit_packs_ok():
    packs = parse_credit_packs(
        '[{"price_id":"price_a","credits":20,"label":"20 shots"}]'
    )
    assert len(packs) == 1
    assert packs[0].price_id == "price_a"
    assert packs[0].credits == 20
    assert packs[0].label == "20 shots"


def test_parse_credit_packs_rejects_bad_credits():
    with pytest.raises(ValueError):
        parse_credit_packs('[{"price_id":"price_a","credits":0,"label":"x"}]')


def test_billing_disabled_without_key(monkeypatch):
    from bebcare.config import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "stripe_secret_key", None)
    monkeypatch.setattr(
        settings_mod.settings,
        "stripe_credit_packs",
        '[{"price_id":"price_a","credits":20,"label":"20"}]',
    )
    assert is_billing_enabled() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/unit/test_stripe_packs.py -v`  
Expected: FAIL（模块不存在）

- [ ] **Step 3: Implement packs + settings**

`backend/bebcare/billing/packs.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass

from bebcare.config.settings import settings


@dataclass(frozen=True)
class CreditPack:
    price_id: str
    credits: int
    label: str


def parse_credit_packs(raw: str) -> list[CreditPack]:
    data = json.loads(raw or "[]")
    if not isinstance(data, list):
        raise ValueError("STRIPE_CREDIT_PACKS must be a JSON array")
    packs: list[CreditPack] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"pack[{i}] must be an object")
        price_id = str(item.get("price_id") or "").strip()
        label = str(item.get("label") or "").strip()
        credits = item.get("credits")
        if not price_id or not label:
            raise ValueError(f"pack[{i}] requires price_id and label")
        if not isinstance(credits, int) or credits < 1:
            raise ValueError(f"pack[{i}] credits must be int >= 1")
        packs.append(CreditPack(price_id=price_id, credits=credits, label=label))
    return packs


def get_credit_packs() -> list[CreditPack]:
    try:
        return parse_credit_packs(settings.stripe_credit_packs)
    except (ValueError, json.JSONDecodeError):
        return []


def find_pack(price_id: str) -> CreditPack | None:
    for p in get_credit_packs():
        if p.price_id == price_id:
            return p
    return None


def is_billing_enabled() -> bool:
    return bool(settings.stripe_secret_key) and len(get_credit_packs()) > 0
```

在 `settings.py` 增加上述四个字段（`billing_contact` 可保留但不再被购买 UI 使用）。

在 `requirements.txt` 增加一行（钉版本，与现有风格一致）：

```text
stripe==11.5.0
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pip install stripe==11.5.0 && python -m pytest tests/unit/test_stripe_packs.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/bebcare/config/settings.py backend/bebcare/billing backend/tests/unit/test_stripe_packs.py
git commit -m "feat(billing): add Stripe settings and credit pack config parser"
```

---

### Task 2: `stripe_checkout_sessions` 模型 + migration + RLS

**Files:**
- Create: `backend/bebcare/models/stripe_checkout.py`
- Modify: `backend/bebcare/models/__init__.py`
- Modify: `backend/bebcare/db/rls_tables.py`
- Create: `backend/migrations/versions/026_stripe_checkout_sessions.py`
- Modify: `backend/bebcare/services/credit_grant_service.py`（导出 `SOURCE_STRIPE`）
- Test: `backend/tests/unit/test_rls_tables.py`（扩展断言）

**Interfaces:**
- Consumes: Alembic `025_image_credit_grants`；`ImageCreditGrant.external_ref`
- Produces:
  - `StripeCheckoutSession` 表字段：`id`, `user_id`, `stripe_session_id`（nullable unique）, `price_id`, `credits`, `status`（`pending|paid|expired`）, `grant_id`（nullable）, `created_at`, `updated_at`
  - `APP_RLS_TABLES` 含 `"stripe_checkout_sessions"`
  - 迁移：创建表；并为 stripe grants 增加部分唯一索引（SQLite + Postgres）：
    - `UNIQUE (external_ref) WHERE source = 'stripe' AND external_ref IS NOT NULL`
  - `SOURCE_STRIPE = "stripe"`

- [ ] **Step 1: Extend RLS test**

在 `backend/tests/unit/test_rls_tables.py` 增加：

```python
assert "stripe_checkout_sessions" in APP_RLS_TABLES
```

- [ ] **Step 2: Run to verify fail**

Run: `cd backend && python -m pytest tests/unit/test_rls_tables.py -v`  
Expected: FAIL

- [ ] **Step 3: Model + migration**

`backend/bebcare/models/stripe_checkout.py`:

```python
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from bebcare.database import Base
import uuid
from datetime import datetime


class StripeCheckoutSession(Base):
    __tablename__ = "stripe_checkout_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stripe_session_id = Column(String(255), nullable=True, unique=True)
    price_id = Column(String(255), nullable=False)
    credits = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, default="pending")  # pending|paid|expired
    grant_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

迁移 `026_stripe_checkout_sessions.py`：`down_revision = "025_image_credit_grants"`；`op.create_table(...)`；`op.create_index` on `user_id`；对 `image_credit_grants` 执行与 025 类似的 partial unique（参考现有 signup_trial 写法）。

注册模型到 `__init__.py`；`rls_tables.py` 追加表名；`credit_grant_service.py` 增加 `SOURCE_STRIPE = "stripe"`。

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_rls_tables.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/bebcare/models/stripe_checkout.py backend/bebcare/models/__init__.py \
  backend/bebcare/db/rls_tables.py backend/migrations/versions/026_stripe_checkout_sessions.py \
  backend/bebcare/services/credit_grant_service.py backend/tests/unit/test_rls_tables.py
git commit -m "feat(billing): add stripe_checkout_sessions table and RLS"
```

---

### Task 3: `stripe_billing_service`（创建 Session + fulfill）

**Files:**
- Create: `backend/bebcare/services/stripe_billing_service.py`
- Test: `backend/tests/unit/test_stripe_billing_service.py`

**Interfaces:**
- Consumes: `StripeCheckoutSession`, `find_pack`, `is_billing_enabled`, `create_grant`, `SOURCE_STRIPE`, `settings`
- Produces:
  - `BillingError(code: str, message: str = "")`
  - `create_checkout_session(db, *, user_id: str, price_id: str) -> tuple[StripeCheckoutSession, str]`  
    返回 `(local_row, checkout_url)`；未启用 / 未知 price → `BillingError`
  - `fulfill_checkout_session(db, *, stripe_session_id: str, metadata: dict) -> StripeCheckoutSession`  
    已 paid 则原样返回；否则标 paid + create_grant，写 `grant_id`
  - Stripe API 调用集中在本文件；测试用 `monkeypatch` 替换 `stripe.checkout.Session.create`

实现要点：

```python
def create_checkout_session(db, *, user_id: str, price_id: str):
    if not is_billing_enabled():
        raise BillingError("billing_disabled")
    pack = find_pack(price_id)
    if pack is None:
        raise BillingError("unknown_price")
    local_id = str(uuid.uuid4())
    row = StripeCheckoutSession(
        id=local_id,
        user_id=user_id,
        price_id=pack.price_id,
        credits=pack.credits,
        status="pending",
    )
    db.add(row)
    db.flush()

    stripe.api_key = settings.stripe_secret_key
    base = settings.frontend_base_url.rstrip("/")
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{"price": pack.price_id, "quantity": 1}],
        success_url=f"{base}/studio?checkout=success",
        cancel_url=f"{base}/studio?checkout=cancel",
        client_reference_id=user_id,
        metadata={
            "user_id": user_id,
            "local_session_id": local_id,
            "credits": str(pack.credits),
            "price_id": pack.price_id,
        },
    )
    row.stripe_session_id = session["id"]
    db.flush()
    return row, session["url"]
```

`fulfill_checkout_session`：

1. 用 `stripe_session_id` 查行；若无，可用 `metadata["local_session_id"]` 查并补写 `stripe_session_id`。
2. 若 `status == "paid"`：return。
3. `credits = int(metadata.get("credits") or row.credits)`；`user_id = metadata.get("user_id") or row.user_id`。
4. 若已存在 `ImageCreditGrant` 且 `source=stripe` 且 `external_ref=stripe_session_id`：标 paid、挂 grant_id、return。
5. 否则 `grant = create_grant(db, user_id=..., quantity=credits, source=SOURCE_STRIPE, external_ref=stripe_session_id, note=f"stripe:{price_id}")`；`row.status="paid"`；`row.grant_id=grant.id`。

- [ ] **Step 1: Write failing unit tests**（mock `stripe.checkout.Session.create`）

```python
def test_create_checkout_session_persists_pending(db_session, monkeypatch):
    # seed user; set settings packs + secret key
    # monkeypatch stripe.checkout.Session.create -> SimpleNamespace(id="cs_test_1", url="https://checkout.stripe.com/test")
    row, url = create_checkout_session(db_session, user_id=user_id, price_id="price_a")
    assert url.startswith("https://")
    assert row.status == "pending"
    assert row.stripe_session_id == "cs_test_1"
    assert row.credits == 20


def test_fulfill_is_idempotent(db_session, monkeypatch):
    # create pending row with stripe_session_id
    fulfill_checkout_session(db_session, stripe_session_id="cs_test_1", metadata={...})
    fulfill_checkout_session(db_session, stripe_session_id="cs_test_1", metadata={...})
    grants = db_session.query(ImageCreditGrant).filter_by(external_ref="cs_test_1").all()
    assert len(grants) == 1
```

（按项目 `conftest` 的 `db_session` / 用户工厂写法对齐；若无用户工厂，参考 `test_credit_grant_service.py`。）

- [ ] **Step 2: Run to verify fail**

Run: `cd backend && python -m pytest tests/unit/test_stripe_billing_service.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement service**

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/bebcare/services/stripe_billing_service.py backend/tests/unit/test_stripe_billing_service.py
git commit -m "feat(billing): Stripe checkout session create and fulfill service"
```

---

### Task 4: Billing HTTP 路由 + `/me.billing_enabled`

**Files:**
- Create: `backend/bebcare/schemas/billing.py`
- Create: `backend/bebcare/api/billing_routes.py`
- Modify: `backend/bebcare/main.py`
- Modify: `backend/bebcare/schemas/auth.py`
- Modify: `backend/bebcare/api/auth_routes.py`
- Test: `backend/tests/api/test_billing_routes.py`

**Interfaces:**
- Consumes: `get_current_active_user`, `get_db`, billing service / packs
- Produces:
  - `GET /v1/billing/credit-packs` → `{ "enabled": bool, "packs": [{"price_id","credits","label"}] }`
  - `POST /v1/billing/checkout-session` body `{ "price_id": str }` → `{ "url": str, "session_id": str }`（本地 id）；403/401 未登录；503 `billing_disabled`；400 `unknown_price`
  - `POST /v1/billing/webhook`：读 `await request.body()`；`stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)`；仅处理 `checkout.session.completed`；成功 `{"received": true}`；验签失败 400
  - `UserResponse.billing_enabled: bool`；`_to_user_response` 设为 `is_billing_enabled()`；`billing_contact` 可继续返回但前端不再使用

`main.py` 挂载：

```python
from bebcare.api.billing_routes import router as billing_router
# credit-packs / checkout-session 在 router 内 Depends(get_current_active_user)
# webhook 路由无用户依赖
api_router.include_router(billing_router)
```

Webhook 路由示例：

```python
@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    if not settings.stripe_webhook_secret:
        raise HTTPException(503, detail="webhook_not_configured")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig, settings.stripe_webhook_secret
        )
    except Exception:
        raise HTTPException(400, detail="invalid_signature")
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        fulfill_checkout_session(
            db,
            stripe_session_id=session["id"],
            metadata=dict(session.get("metadata") or {}),
        )
        db.commit()
    return {"received": True}
```

Router prefix: `/billing`（最终路径 `/v1/billing/...`）。

- [ ] **Step 1: API tests**

```python
def test_credit_packs_disabled_by_default(full_client, auth_headers):
    # clear stripe key via monkeypatch on settings
    r = full_client.get("/v1/billing/credit-packs", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["enabled"] is False


def test_checkout_returns_503_when_disabled(full_client, auth_headers):
    r = full_client.post(
        "/v1/billing/checkout-session",
        headers=auth_headers,
        json={"price_id": "price_a"},
    )
    assert r.status_code == 503


def test_webhook_fulfill_grants_credits(full_client, auth_headers, monkeypatch, db...):
    # enable billing; create pending row; mock construct_event to return completed event
    # POST /v1/billing/webhook with any body + header
    # assert me.image_credits_remaining increased
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement routes + auth schema 变更**

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/bebcare/schemas/billing.py backend/bebcare/api/billing_routes.py \
  backend/bebcare/main.py backend/bebcare/schemas/auth.py backend/bebcare/api/auth_routes.py \
  backend/tests/api/test_billing_routes.py
git commit -m "feat(billing): add Stripe credit-packs, checkout, and webhook routes"
```

---

### Task 5: 前端购买弹窗 + i18n + 回站刷新

**Files:**
- Create: `frontend/src/api/billing.ts`
- Modify: `frontend/src/api/auth.ts`
- Modify: `frontend/src/components/SubscribeCreditsModal.tsx`
- Modify: `frontend/src/components/ImageModelPicker.tsx`
- Modify: `frontend/src/i18n/locales/pages.ts`
- Modify: `frontend/src/pages/Studio.tsx`（若 checkout query 在此处理；否则在 `ImageModelPicker` / layout）

**Interfaces:**
- Consumes: `/v1/billing/*`、`/auth/me`
- Produces:
  - `listCreditPacks(): Promise<{enabled:boolean; packs: CreditPack[]}>`
  - `createCheckoutSession(priceId: string): Promise<{url:string; session_id:string}>`
  - Modal：`enabled` 时列出 packs，点击「购买」调用 checkout 并 `window.location.href = url`
  - `enabled=false`：按钮 `disabled` + 文案「在线购买暂未开通」
  - 移除 `billingContact` props 与联系 CTA
  - `UserResponse.billing_enabled?: boolean`
  - 进入 Studio 若 `checkout=success`：toast/文案提示并 `getMe` 刷新额度，然后 `history.replace` 清 query

`frontend/src/api/billing.ts`:

```typescript
import axiosInstance from './axiosInstance';

export interface CreditPack {
  price_id: string;
  credits: number;
  label: string;
}

export async function listCreditPacks(): Promise<{
  enabled: boolean;
  packs: CreditPack[];
}> {
  const { data } = await axiosInstance.get('/billing/credit-packs');
  return data;
}

export async function createCheckoutSession(priceId: string): Promise<{
  url: string;
  session_id: string;
}> {
  const { data } = await axiosInstance.post('/billing/checkout-session', {
    price_id: priceId,
  });
  return data;
}
```

i18n 键（中英都改）：

- `subscribeCredits.body` → 说明在线支付购买次数包
- 删除依赖 `contactCta` 的 UI；可改键为 `buyCta` / `unavailable` / `packCredits`
- `subscribeCredits.checkoutSuccess` → 「支付成功，次数即将到账」
- `subscribeCredits.checkoutCancel` → 「已取消支付」

- [ ] **Step 1: 实现 API + 重写 Modal + 去掉 ImageModelPicker 的 billingContact**

- [ ] **Step 2: 手动冒烟（无密钥）** — 打开 Studio，购买按钮应禁用

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/billing.ts frontend/src/api/auth.ts \
  frontend/src/components/SubscribeCreditsModal.tsx frontend/src/components/ImageModelPicker.tsx \
  frontend/src/i18n/locales/pages.ts frontend/src/pages/Studio.tsx
git commit -m "feat(billing): Stripe checkout UI for credit packs"
```

---

### Task 6: 文档、env 示例、部署副本同步

**Files:**
- Modify: `backend/.env.example`
- Modify: `README.md`（Billing / Stripe 沙盒小节）
- Run: `python scripts/sync_deploy_copies.py`

**文档片段写入 `.env.example`：**

```env
# Stripe（测试模式；空则关闭在线购买）
# STRIPE_SECRET_KEY=sk_test_...
# STRIPE_WEBHOOK_SECRET=whsec_...
# STRIPE_CREDIT_PACKS=[{"price_id":"price_xxx","credits":20,"label":"20 credits"}]
# FRONTEND_BASE_URL=http://localhost:5174
```

README 增加简短步骤：

1. Dashboard 开 Test mode，创建 Product + Price，复制 `price_...`
2. 填 `STRIPE_SECRET_KEY` / `STRIPE_CREDIT_PACKS` / `FRONTEND_BASE_URL`
3. 本地 webhook：`stripe listen --forward-to localhost:8888/v1/billing/webhook`，把打印的 `whsec_` 写入 `STRIPE_WEBHOOK_SECRET`
4. 用测试卡 `4242…` 走完 Checkout，确认 `/auth/me` 额度增加

- [ ] **Step 1: 更新 `.env.example` + README**

- [ ] **Step 2: 同步部署副本**

Run: `python scripts/sync_deploy_copies.py`  
Expected: OK，无 drift

- [ ] **Step 3: 全量相关测试**

Run: `cd backend && python -m pytest tests/unit/test_stripe_packs.py tests/unit/test_stripe_billing_service.py tests/api/test_billing_routes.py tests/unit/test_rls_tables.py -v`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/.env.example README.md hf-space space4
git commit -m "docs(billing): Stripe sandbox setup and sync deploy copies"
```

---

## 沙盒验收清单（人工）

- [ ] Test mode Product/Price 已创建，`price_id` 写入 `STRIPE_CREDIT_PACKS`
- [ ] `stripe listen` 转发 webhook，签名密钥正确
- [ ] 登录用户点击购买 → Stripe Checkout → 测试卡支付成功
- [ ] 回站 `?checkout=success`，额度 = 原额度 + pack.credits
- [ ] 同一 session 重复投递 webhook，额度不双倍
- [ ] 清空 `STRIPE_SECRET_KEY` 后购买按钮不可用

---

## Self-review（计划作者）

| Spec 要求 | 对应 Task |
|-----------|-----------|
| Hosted Checkout + webhook 发 grant | 3, 4 |
| 配置映射 SKU / GET credit-packs | 1, 4, 5 |
| `stripe_checkout_sessions` 表 | 2, 3 |
| 移除联系入口；无密钥不可买 | 4, 5 |
| 幂等 | 3 |
| 沙盒文档 | 6 |
| hf-space 同步 | 6 |

无 TBD；类型名在 Task 间一致：`CreditPack`、`StripeCheckoutSession`、`create_checkout_session`、`fulfill_checkout_session`、`is_billing_enabled`。
