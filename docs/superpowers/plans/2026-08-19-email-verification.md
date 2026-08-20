# 邮箱验证码认证 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 Resend 发送 6 位邮箱验证码，覆盖公开注册（先码后号）、忘记密码、已登录改密；存量用户视为已验证。

**Architecture:** 独立表 `email_verification_codes` 存码哈希与用途；`email_sender` 调 Resend（开发可日志打码）；`email_code_service` 负责生成/限流/校验/作废；`auth_routes` 暴露发码与三条消费流。前端 Signup 两步、新 ForgotPassword 页、侧栏改密弹窗。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、httpx、pytest、React、i18n。发信仅 Resend HTTP API（不引入官方 SDK，与现有 httpx 一致）。

**Spec:** [`docs/superpowers/specs/2026-08-19-email-verification-design.md`](../specs/2026-08-19-email-verification-design.md)

## Global Constraints

- 发信：**仅 Resend**；生产必须配置 `RESEND_API_KEY` + `EMAIL_FROM`。
- 注册：验证码通过后才建号；密码**不**写入 `payload_json`。
- 忘记密码：邮箱不存在仍返回成功（防枚举）。
- 已登录改密：只要验证码 + 新密码；邮箱取当前用户，忽略客户端伪造。
- 存量用户 / 管理员建号：`email_verified_at` 立即有值；登录**不**因未验证拒绝。
- 对外验证码错误统一模糊文案：`Invalid or expired verification code`（前端 i18n 映射）。
- `hf-space/bebcare/` 与 `backend/bebcare/`、`hf-space/migrations/` 与 `backend/migrations/` 镜像同步。
- 测试在 `backend/` 下：`python -m pytest tests/path -v`
- 首版不做：magic link、改绑邮箱、短信、管理员改他人密码发信、refresh 服务端吊销、SMTP。

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/bebcare/config/settings.py` | Resend / 码 TTL / 限流 / 开发打码开关 |
| `backend/bebcare/services/email_sender.py` | Resend HTTP 发信；开发日志回退 |
| `backend/bebcare/models/email_verification.py` | `EmailVerificationCode` 模型 |
| `backend/bebcare/models/user.py` | `email_verified_at` |
| `backend/migrations/versions/025_email_verification.py` | 加列 + 新表 + 回填 + RLS 清单注册 |
| `backend/bebcare/db/rls_tables.py` | 加入 `email_verification_codes` |
| `backend/bebcare/services/email_code_service.py` | 生成、哈希、冷却、日限、校验、消费 |
| `backend/bebcare/schemas/auth.py` | `SendEmailCodeRequest` 等 |
| `backend/bebcare/api/auth_routes.py` | 发码、注册带码、重置、改密 |
| `backend/tests/unit/test_email_sender.py` | sender 单元测试 |
| `backend/tests/unit/test_email_code_service.py` | 码服务单元测试 |
| `backend/tests/api/test_email_auth_flows.py` | API 集成（Mock sender） |
| `frontend/src/api/auth.ts` | `sendEmailCode` / `resetPassword` / `changeMyPassword` |
| `frontend/src/api/axiosInstance.ts` | 401 白名单扩展 |
| `frontend/src/pages/Signup.tsx` | 两步注册 |
| `frontend/src/pages/ForgotPassword.tsx` | 忘记密码页 |
| `frontend/src/pages/Login.tsx` | 忘记密码链接 |
| `frontend/src/components/ChangePasswordModal.tsx` | 改密弹窗 |
| `frontend/src/components/Sidebar.tsx` | 入口 |
| `frontend/src/App.tsx` | `/forgot-password` 路由 |
| `frontend/src/i18n/locales/zh.base.ts` / `en.base.ts` | 文案 |
| `README.md`（或现有 env 文档段） | 记录 Resend 环境变量 |
| `hf-space/...` | 与 backend 对应文件镜像 |

---

### Task 1: Settings + Resend email_sender

**Files:**
- Modify: `backend/bebcare/config/settings.py`
- Create: `backend/bebcare/services/email_sender.py`
- Test: `backend/tests/unit/test_email_sender.py`

**Interfaces:**
- Consumes: `settings`
- Produces:
  - Settings fields: `resend_api_key: str | None = None`, `email_from: str = "PulseForge <onboarding@resend.dev>"`, `email_code_ttl_seconds: int = 600`, `email_code_resend_cooldown_seconds: int = 60`, `email_code_max_attempts: int = 5`, `email_code_daily_limit_per_email: int = 10`, `email_dev_log_codes: bool = False`
  - `class EmailSendError(Exception)`
  - `def can_send_email() -> bool`
  - `def send_verification_email(*, to: str, code: str, purpose: str) -> None`  
    - 有 Key：`POST https://api.resend.com/emails`，Bearer Key，JSON `{from, to:[to], subject, html}`  
    - 无 Key 且 `settings.is_development` 或 `email_dev_log_codes`：`logger.info("DEV email code to=%s purpose=%s code=%s", ...)` 后 return  
    - 否则：`raise EmailSendError("Email delivery is not configured")`  
    - HTTP 非 2xx：`raise EmailSendError("Failed to send email")`（不暴露 Resend 原文给上层可选包装）

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/unit/test_email_sender.py
from unittest.mock import MagicMock, patch
import pytest
from bebcare.services.email_sender import send_verification_email, EmailSendError, can_send_email


def test_dev_log_without_api_key(monkeypatch):
    from bebcare.config import settings as settings_mod
    monkeypatch.setattr(settings_mod.settings, "resend_api_key", None)
    monkeypatch.setattr(settings_mod.settings, "app_env", "development")
    monkeypatch.setattr(settings_mod.settings, "email_dev_log_codes", True)
    # should not raise
    send_verification_email(to="a@test.local", code="123456", purpose="register")


def test_production_without_key_raises(monkeypatch):
    from bebcare.config import settings as settings_mod
    monkeypatch.setattr(settings_mod.settings, "resend_api_key", None)
    monkeypatch.setattr(settings_mod.settings, "app_env", "production")
    monkeypatch.setattr(settings_mod.settings, "email_dev_log_codes", False)
    with pytest.raises(EmailSendError):
        send_verification_email(to="a@test.local", code="123456", purpose="register")


@patch("bebcare.services.email_sender.httpx.Client")
def test_resend_http_ok(mock_client_cls, monkeypatch):
    from bebcare.config import settings as settings_mod
    monkeypatch.setattr(settings_mod.settings, "resend_api_key", "re_test")
    monkeypatch.setattr(settings_mod.settings, "email_from", "App <noreply@example.com>")
    mock_resp = MagicMock(status_code=200)
    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.post.return_value = mock_resp
    mock_client_cls.return_value = mock_client
    send_verification_email(to="a@test.local", code="654321", purpose="reset_password")
    args, kwargs = mock_client.post.call_args
    assert args[0] == "https://api.resend.com/emails"
    assert kwargs["json"]["to"] == ["a@test.local"]
    assert "654321" in kwargs["json"]["html"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_email_sender.py -v`  
Expected: FAIL（模块不存在）

- [ ] **Step 3: Implement settings + sender**

在 `settings.py` 的「安全配置」段落后增加上述字段（env 名：`RESEND_API_KEY`、`EMAIL_FROM`、`EMAIL_CODE_TTL_SECONDS` 等，pydantic-settings 默认映射）。

`email_sender.py` 用 `httpx.Client(timeout=15.0)`；`purpose` 映射简短中英 subject/html（register / reset_password / change_password）。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_email_sender.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/bebcare/config/settings.py backend/bebcare/services/email_sender.py backend/tests/unit/test_email_sender.py
git commit -m "feat: add Resend email sender and email settings"
```

---

### Task 2: Models + migration + RLS 清单

**Files:**
- Modify: `backend/bebcare/models/user.py`
- Create: `backend/bebcare/models/email_verification.py`
- Modify: `backend/bebcare/models/__init__.py`
- Create: `backend/migrations/versions/025_email_verification.py`
- Modify: `backend/bebcare/db/rls_tables.py`（追加 `"email_verification_codes"`）
- Mirror: `hf-space/bebcare/models/...`、`hf-space/migrations/versions/025_email_verification.py`、`hf-space/bebcare/db/rls_tables.py`

**Interfaces:**
- Produces:
  - `User.email_verified_at: Optional[datetime]`
  - `class EmailVerificationCode(Base)`：字段与 spec 一致：`id`, `email`, `purpose`, `code_hash`, `payload_json` (Text/JSON 可空), `expires_at`, `attempts` (int default 0), `consumed_at`, `created_at`, `owner_user_id` (可空 String 36)
  - 迁移 `025_email_verification`：`down_revision = "024_prompt_dimension_owner"`
  - upgrade：`users.email_verified_at` 可空 → `UPDATE users SET email_verified_at = created_at WHERE email_verified_at IS NULL` → 建表 + 索引 `(email, purpose, created_at)` → 若 Postgres：`ALTER TABLE email_verification_codes ENABLE ROW LEVEL SECURITY`（与 023 风格一致，无 POLICY）

- [ ] **Step 1: Write a small migration/model smoke test expectation in unit test**

```python
# backend/tests/unit/test_email_verification_model.py
from bebcare.models.email_verification import EmailVerificationCode
from bebcare.models.user import User
from bebcare.db.rls_tables import APP_RLS_TABLES


def test_user_has_email_verified_at_column():
    assert hasattr(User, "email_verified_at")


def test_code_model_tablename():
    assert EmailVerificationCode.__tablename__ == "email_verification_codes"


def test_rls_list_includes_codes():
    assert "email_verification_codes" in APP_RLS_TABLES
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/unit/test_email_verification_model.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement model + migration + rls_tables；同步 hf-space**

迁移参考 `024_prompt_dimension_owner.py` 的 Postgres/SQLite 兼容写法；`batch_alter_table` 加列。

- [ ] **Step 4: Run tests + 本地 migrate（SQLite）**

Run:
```bash
python -m pytest tests/unit/test_email_verification_model.py tests/unit/test_rls_tables.py -v
# 若本地 DB 需升级：
# alembic upgrade head
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/bebcare/models/user.py backend/bebcare/models/email_verification.py backend/bebcare/models/__init__.py backend/migrations/versions/025_email_verification.py backend/bebcare/db/rls_tables.py backend/tests/unit/test_email_verification_model.py hf-space/bebcare/models/user.py hf-space/bebcare/models/email_verification.py hf-space/bebcare/models/__init__.py hf-space/migrations/versions/025_email_verification.py hf-space/bebcare/db/rls_tables.py
git commit -m "feat: add email verification models and migration"
```

---

### Task 3: email_code_service

**Files:**
- Create: `backend/bebcare/services/email_code_service.py`
- Test: `backend/tests/unit/test_email_code_service.py`
- Mirror: `hf-space/bebcare/services/email_code_service.py`

**Interfaces:**
- Consumes: `Session`, `EmailVerificationCode`, `send_verification_email`, settings
- Produces:
  - `PURPOSE_REGISTER = "register"` / `PURPOSE_RESET = "reset_password"` / `PURPOSE_CHANGE = "change_password"`
  - `class EmailCodeError(Exception)` with `.code` in `{"cooldown","daily_limit","invalid","send_failed"}` 及可选 `retry_after: int | None`
  - `def normalize_email(email: str) -> str` → `email.strip().lower()`
  - `def hash_code(code: str) -> str` → `hmac.new(settings.secret_key.encode(), code.encode(), hashlib.sha256).hexdigest()`
  - `def create_and_send_code(db, *, email: str, purpose: str, payload: dict | None = None, owner_user_id: str | None = None) -> None`  
    - 冷却：若同 email+purpose 最近一条 `created_at` 在 cooldown 内 → `EmailCodeError(cooldown)`  
    - 日限：过去 24h 同 email 条数 ≥ limit → `EmailCodeError(daily_limit)`  
    - 作废旧未消费：同 email+purpose 且 `consumed_at IS NULL` → 设 `consumed_at=now()`  
    - 生成 `secrets.choice` 6 位数字字符串；入库；调用 `send_verification_email`；失败则 rollback 本条或标消费并 `raise EmailCodeError(send_failed)`
  - `def verify_and_consume(db, *, email: str, purpose: str, code: str, expected_payload: dict | None = None) -> EmailVerificationCode`  
    - 取最新未消费记录；过期 / 无记录 / attempts≥max → invalid 并 consume 超限条  
    - 哈希比对失败：attempts+=1，commit，raise invalid  
    - payload：若 `expected_payload` 提供，要求 row.payload_json 解析后包含相同键值（至少 `username`）  
    - 成功：`consumed_at=now()`，return row

- [ ] **Step 1: Write failing unit tests（用 SQLite Session fixture 或 MagicMock 精简）**

优先复用 `tests/conftest.py` 的 db fixture（若有）。若无，用临时 SQLite：

```python
# backend/tests/unit/test_email_code_service.py
from datetime import datetime, timedelta
from unittest.mock import patch
import pytest
from bebcare.services import email_code_service as svc


def test_hash_code_stable(monkeypatch):
    from bebcare.config import settings as settings_mod
    monkeypatch.setattr(settings_mod.settings, "secret_key", "test-secret")
    assert svc.hash_code("123456") == svc.hash_code("123456")
    assert svc.hash_code("123456") != svc.hash_code("000000")


@patch("bebcare.services.email_code_service.send_verification_email")
def test_create_and_verify_roundtrip(mock_send, db_session, monkeypatch):
    from bebcare.config import settings as settings_mod
    monkeypatch.setattr(settings_mod.settings, "email_code_ttl_seconds", 600)
    monkeypatch.setattr(settings_mod.settings, "email_code_resend_cooldown_seconds", 0)
    monkeypatch.setattr(settings_mod.settings, "email_code_daily_limit_per_email", 100)
    # capture code from send call
    sent = {}
    def _capture(**kwargs):
        sent["code"] = kwargs["code"]
    mock_send.side_effect = _capture
    svc.create_and_send_code(
        db_session,
        email="User@Test.Local",
        purpose=svc.PURPOSE_REGISTER,
        payload={"username": "alice"},
    )
    row = svc.verify_and_consume(
        db_session,
        email="user@test.local",
        purpose=svc.PURPOSE_REGISTER,
        code=sent["code"],
        expected_payload={"username": "alice"},
    )
    assert row.consumed_at is not None


@patch("bebcare.services.email_code_service.send_verification_email")
def test_cooldown(mock_send, db_session, monkeypatch):
    from bebcare.config import settings as settings_mod
    monkeypatch.setattr(settings_mod.settings, "email_code_resend_cooldown_seconds", 60)
    monkeypatch.setattr(settings_mod.settings, "email_code_daily_limit_per_email", 100)
    svc.create_and_send_code(db_session, email="a@t.local", purpose=svc.PURPOSE_RESET)
    with pytest.raises(svc.EmailCodeError) as ei:
        svc.create_and_send_code(db_session, email="a@t.local", purpose=svc.PURPOSE_RESET)
    assert ei.value.code == "cooldown"
```

若 `db_session` 不存在：在本文件内用 `conftest` 同款建表，或扩展 `conftest.py` 导出 session（最小改动）。

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/unit/test_email_code_service.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement service**

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/unit/test_email_code_service.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/bebcare/services/email_code_service.py backend/tests/unit/test_email_code_service.py hf-space/bebcare/services/email_code_service.py
git commit -m "feat: add email verification code service"
```

---

### Task 4: Auth schemas + routes（发码 / 注册 / 重置 / 改密）

**Files:**
- Modify: `backend/bebcare/schemas/auth.py`
- Modify: `backend/bebcare/api/auth_routes.py`
- Modify: `backend/bebcare/initial_data.py`（若创建 admin 时写 `email_verified_at=now()`）
- Test: `backend/tests/api/test_email_auth_flows.py`
- Mirror: `hf-space/bebcare/schemas/auth.py`、`hf-space/bebcare/api/auth_routes.py`、`hf-space/bebcare/initial_data.py`

**Interfaces:**
- Schemas:
  - `SendEmailCodeRequest`: `email: Optional[EmailStr] = None`, `purpose: Literal["register","reset_password","change_password"]`, `username: Optional[str] = None`
  - `SendEmailCodeResponse`: `message: str`, `cooldown_seconds: int`
  - `UserCreate`: 公开注册改为必填 `email: EmailStr` + 必填 `code: str = Field(..., min_length=6, max_length=6)`；管理员建号路径继续用可选 email、无 code（可另建 `AdminUserCreate` 或路由内分支：有 code 走公开规则）
  - **推荐：** 保留 `UserCreate` 给管理员（email 可选、无 code）；新增 `PublicRegisterRequest(username, email: EmailStr, password, code: str)` 专用于 `/register/`
  - `PasswordResetRequest`: `email: EmailStr`, `code: str`, `new_password: str = Field(..., min_length=6)`
  - `ChangePasswordRequest`: `code: str`, `new_password: str = Field(..., min_length=6)`
- Routes:
  - `POST /auth/email/send-code` → 按 purpose 分支（见下）
  - `POST /auth/register/` → 校验码后建用户，`email_verified_at=utcnow()`，返回 tokens
  - `POST /auth/password/reset` → 校验码后改密
  - `POST /auth/me/password` → 需登录；校验码后改密
  - `POST /auth/users`（管理员）：创建时 `email_verified_at=utcnow()`

**send-code 分支逻辑：**

| purpose | 鉴权 | 行为 |
|---------|------|------|
| register | 公开 | `allow_public_signup` 否则 403；需 email+username；占用则 400；`create_and_send_code(..., payload={username})` |
| reset_password | 公开 | 需 email；用户不存在 → 仍 200 成功文案、不发信；存在则发码 |
| change_password | 登录 | 忽略 body.email；用 `current_user.email`；`owner_user_id=current_user.user_id` |

错误映射：
- `EmailCodeError(cooldown)` → 429，`detail` 含 retry，`headers={"Retry-After": str(n)}`
- `daily_limit` / `send_failed` → 503 或 400 固定文案 `"Unable to send email right now"`
- verify invalid → 400 `"Invalid or expired verification code"`

- [ ] **Step 1: Write API tests with Mock send**

```python
# backend/tests/api/test_email_auth_flows.py
from unittest.mock import patch


@patch("bebcare.services.email_code_service.send_verification_email")
def test_register_requires_code(mock_send, client, monkeypatch):
    from bebcare.config import settings as settings_mod
    monkeypatch.setattr(settings_mod.settings, "allow_public_signup", True)
    monkeypatch.setattr(settings_mod.settings, "email_code_resend_cooldown_seconds", 0)
    sent = {}
    mock_send.side_effect = lambda **kw: sent.update(code=kw["code"])
    r1 = client.post("/v1/auth/email/send-code", json={
        "email": "new@test.local",
        "purpose": "register",
        "username": "newuser1",
    })
    assert r1.status_code == 200, r1.text
    bad = client.post("/v1/auth/register/", json={
        "username": "newuser1",
        "email": "new@test.local",
        "password": "Pass123!",
        "code": "000000",
    })
    assert bad.status_code == 400
    ok = client.post("/v1/auth/register/", json={
        "username": "newuser1",
        "email": "new@test.local",
        "password": "Pass123!",
        "code": sent["code"],
    })
    assert ok.status_code == 201, ok.text
    assert ok.json()["access_token"]


@patch("bebcare.services.email_code_service.send_verification_email")
def test_reset_unknown_email_no_enumeration(mock_send, client):
    r = client.post("/v1/auth/email/send-code", json={
        "email": "nobody@test.local",
        "purpose": "reset_password",
    })
    assert r.status_code == 200
    mock_send.assert_not_called()


@patch("bebcare.services.email_code_service.send_verification_email")
def test_change_password_flow(mock_send, client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        __import__("bebcare.config.settings", fromlist=["settings"]).settings,
        "email_code_resend_cooldown_seconds",
        0,
    )
    sent = {}
    mock_send.side_effect = lambda **kw: sent.update(code=kw["code"])
    r1 = client.post(
        "/v1/auth/email/send-code",
        headers=auth_headers,
        json={"purpose": "change_password"},
    )
    assert r1.status_code == 200, r1.text
    r2 = client.post(
        "/v1/auth/me/password",
        headers=auth_headers,
        json={"code": sent["code"], "new_password": "NewPass123!"},
    )
    assert r2.status_code == 200, r2.text
```

另测：无码注册 422；signup disabled 403；reset 成功后可用新密码登录。

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/api/test_email_auth_flows.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement schemas + routes**

- [ ] **Step 4: Run full related tests**

Run:
```bash
python -m pytest tests/api/test_email_auth_flows.py tests/api/test_auth_and_generate.py -v
```
Expected: PASS（注意：旧 `test_create_user_without_trailing_slash` 仍走管理员路径，不受公开 register 影响）

- [ ] **Step 5: Commit**

```bash
git add backend/bebcare/schemas/auth.py backend/bebcare/api/auth_routes.py backend/bebcare/initial_data.py backend/tests/api/test_email_auth_flows.py hf-space/bebcare/schemas/auth.py hf-space/bebcare/api/auth_routes.py hf-space/bebcare/initial_data.py
git commit -m "feat: wire email code into register, reset, and change-password APIs"
```

---

### Task 5: Frontend API 客户端 + axios 白名单

**Files:**
- Modify: `frontend/src/api/auth.ts`
- Modify: `frontend/src/api/axiosInstance.ts`

**Interfaces:**
- Produces:
  - `sendEmailCode(data: { email?: string; purpose: 'register'|'reset_password'|'change_password'; username?: string }) => Promise<{ message: string; cooldown_seconds: number }>`
  - `register` body 增加 `code: string`
  - `resetPassword({ email, code, new_password })`
  - `changeMyPassword({ code, new_password })`
- axios `authPaths` 增加：`/auth/email/send-code`、`/auth/password/reset`（以及已有 login/register/refresh）

- [ ] **Step 1: 更新 auth.ts 与 axiosInstance.ts**（类型与函数如上）

- [ ] **Step 2: Typecheck（若项目有）**

Run: `cd frontend && npx tsc -p tsconfig.app.json --noEmit`（或现有 `npm run build` 的类型检查脚本）  
Expected: 无因 auth API 引入的错误（Signup 尚未改时可临时让 `register` 的 `code` 为必填——下一 Task 立刻接上；或本 Task 与 Task 6 同会话完成）

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/auth.ts frontend/src/api/axiosInstance.ts
git commit -m "feat: add frontend email-code auth API helpers"
```

---

### Task 6: Signup 两步 + ForgotPassword + Login 链接

**Files:**
- Modify: `frontend/src/pages/Signup.tsx`
- Create: `frontend/src/pages/ForgotPassword.tsx`
- Modify: `frontend/src/pages/Login.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/i18n/locales/zh.base.ts`、`en.base.ts`（本 Task 先加 signup/forgot 键；改密键可 Task 7）

**UI 行为：**
- Signup：`step` state `form | code`；form 提交调 `sendEmailCode` 成功后进入 code；code 页输入 6 位后 `register({..., code})`；显示倒计时 `cooldown_seconds` 禁用重发
- Login：密码框下增加 `Link to="/forgot-password"`
- ForgotPassword：复用 `AuthLayout`；流程同「邮箱 → 发码 → 码+新密码」；成功 `navigate('/login')`
- App：`PublicOnlyRoute` 下增加 `/forgot-password`

- [ ] **Step 1: 实现页面与路由 + 最小 i18n 键**

必需键示例（中英都加）：
- `signup.sendCode` / `signup.resendCode` / `signup.code` / `signup.codeHint` / `signup.cooldown`
- `login.forgotPassword`
- `forgotPassword.title` / `subtitle` / `submit` / `success` / `sendCode` 等

- [ ] **Step 2: 手动或 Playwright 不做强制；跑前端 build**

Run: `cd frontend && npm run build`  
Expected: 成功

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Signup.tsx frontend/src/pages/ForgotPassword.tsx frontend/src/pages/Login.tsx frontend/src/App.tsx frontend/src/i18n/locales/zh.base.ts frontend/src/i18n/locales/en.base.ts
git commit -m "feat: signup OTP and forgot-password pages"
```

---

### Task 7: 已登录改密弹窗

**Files:**
- Create: `frontend/src/components/ChangePasswordModal.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`（登出旁增加「修改密码」按钮，打开 modal）
- Modify: i18n `zh.base.ts` / `en.base.ts`（`changePassword.*`）

**UI：** 模态：发送验证码 → 输入码 + 新密码 → `changeMyPassword`；成功关闭并 toast/alert；会话保持。

- [ ] **Step 1: 实现 Modal + Sidebar 入口 + i18n**

- [ ] **Step 2: `npm run build`**

Expected: 成功

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ChangePasswordModal.tsx frontend/src/components/Sidebar.tsx frontend/src/i18n/locales/zh.base.ts frontend/src/i18n/locales/en.base.ts
git commit -m "feat: add change-password modal with email OTP"
```

---

### Task 8: 文档环境变量 + 最终回归

**Files:**
- Modify: `README.md`（现有 `ADMIN_EMAIL` 段附近增加 Resend 变量表）
- 确认 hf-space 镜像：`settings.py`、`email_sender.py`、`email_code_service.py`、auth 相关已在前序 Task 同步；本 Task 做 diff 核对

- [ ] **Step 1: README 增加**

```markdown
### Email (Resend)
- `RESEND_API_KEY` — required in production
- `EMAIL_FROM` — verified sender, e.g. `PulseForge <noreply@yourdomain.com>`
- `EMAIL_CODE_TTL_SECONDS` — default 600
- `EMAIL_CODE_RESEND_COOLDOWN_SECONDS` — default 60
- `EMAIL_DEV_LOG_CODES` — development only: log codes when key missing
```

- [ ] **Step 2: 全量相关 pytest**

Run:
```bash
cd backend
python -m pytest tests/unit/test_email_sender.py tests/unit/test_email_code_service.py tests/unit/test_email_verification_model.py tests/api/test_email_auth_flows.py tests/api/test_auth_and_generate.py -v
```
Expected: 全部 PASS

- [ ] **Step 3: 核对 hf-space 与 backend 关键文件一致（关键路径）**

```bash
# PowerShell 示例：比较文件是否存在且大小接近；有差异则复制
diff backend/bebcare/services/email_sender.py hf-space/bebcare/services/email_sender.py
```

- [ ] **Step 4: Commit**

```bash
git add README.md
# 若有遗漏的 hf-space 同步文件一并 add
git commit -m "docs: document Resend email verification env vars"
```

---

## Spec coverage checklist

| Spec 项 | Task |
|---------|------|
| Resend 发信 + 开发日志码 | 1 |
| `email_verified_at` + 存量回填 | 2 |
| `email_verification_codes` 表 + RLS | 2 |
| 码哈希 / 冷却 / 日限 / 消费 | 3 |
| 发码 API + 注册先码后号 | 4 |
| 忘记密码防枚举 | 4 |
| 已登录改密 | 4, 7 |
| 管理员建号已验证 | 4 |
| Signup 两步 / ForgotPassword / Login 链接 | 6 |
| 改密 UI | 7 |
| axios 白名单 | 5 |
| i18n | 6, 7 |
| 环境变量文档 | 8 |
| hf-space 镜像 | 2–4, 8 |
| 不做 magic link / SMTP / refresh 吊销 | 全局约束 |

---

## Self-review notes

- 无 TBD；公开注册与管理员建号用不同 schema，避免管理员 API 被强制 `code`。
- `verify_and_consume` 与 `create_and_send_code` 签名在 Task 3/4 一致。
- IP 限流：spec 为可选；本计划以邮箱限流为主（YAGNI）。
