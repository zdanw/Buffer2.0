# 邮箱验证码认证设计

**日期：** 2026-08-19  
**状态：** 已定稿（待实现）  
**背景：** 公开注册已强制填写邮箱，但不会发信、不会校验；无忘记密码 / 自助改密流程。部署在 HF Space + Vercel，适合用 HTTP API 发信而非自建 SMTP。

## 目标

- 公开注册：邮件验证码通过后才创建账号并登录（无未验证垃圾账号）。
- 未登录：邮箱 + 验证码 + 新密码 找回密码。
- 已登录：邮箱验证码 + 新密码 修改密码（不要求当前密码）。
- 存量用户与管理员手工建号：视为已验证，不打断现有登录。
- 发信走 **Resend API**；验证码哈希入库，可限流、可测。

## 现状摘要

- 认证：自建 JWT（access + refresh）；公开注册由 `allow_public_signup` 控制。
- `User` 有必填 `email`，无 `email_verified_at`；`POST /auth/register/` 校验占用后直接建号并返回 token。
- 无 SMTP / Resend / 验证码表；无忘记密码页；管理员 `UserManagement` 可直接改他人密码。
- 相关锚点：`backend/bebcare/api/auth_routes.py`、`backend/bebcare/models/user.py`、`frontend/src/pages/Signup.tsx`、`frontend/src/api/auth.ts`。

## 方案选择

采用 **方案 1：验证码表 + Resend**。

未采用：签名 JWT 作待验证票据（限流/审计弱、多实例难控）；整包换 Supabase Auth / Clerk（与现有 JWT 用户表及数据隔离冲突，改动面过大）。

### 已确认产品决策

| 项 | 决策 |
|----|------|
| 发信 | Resend API |
| 注册顺序 | 先发码，校验通过后再建号并登录 |
| 找回 / 改密 | 两者都做 |
| 存量用户 | 全部视为已验证；仅新公开注册强制验证 |
| 已登录改密 | 只要邮箱验证码 + 新密码（不要当前密码） |

---

## §1 数据模型与 API 流程

### User 增量

- 新增 `email_verified_at`（可空 `DateTime`）。
- 迁移：存量用户回填为已验证（建议 `email_verified_at = created_at`）。
- 新公开注册：验证码通过后创建用户时写入 `email_verified_at = now()`。
- 管理员 `POST /auth/users` 手工建号：创建时直接写入 `email_verified_at = now()`。

首版登录**不**因 `email_verified_at` 为空拒绝（存量已回填；后续若要强制可再加）。

### 新表 `email_verification_codes`

| 字段 | 说明 |
|------|------|
| `id` | UUID 主键 |
| `email` | 目标邮箱（规范化小写） |
| `purpose` | `register` / `reset_password` / `change_password` |
| `code_hash` | 验证码哈希（不存明文） |
| `payload_json` | 可选；注册发码时可暂存 `username`（**密码不落库**，由前端保留至提交注册） |
| `expires_at` | 默认 10 分钟 |
| `attempts` | 失败次数；超限作废 |
| `consumed_at` | 用过后作废 |
| `created_at` | 创建时间 |
| `owner_user_id` | 可空；`change_password` 时可记当前用户，便于审计 |

索引建议：`(email, purpose, created_at)`；查询未消费且未过期的最新一条。

### 注册流程（先码后号）

1. `POST /auth/email/send-code`  
   Body：`{ email, purpose: "register", username }`  
   - 若 `allow_public_signup` 为 false → 403  
   - 校验 username / email 未被占用  
   - 生成 6 位数字码，哈希入库，Resend 发信  
   - 同一 `email + purpose` 冷却（默认 60s）
2. 前端本地保留 `password`（不写库）。
3. `POST /auth/register/`  
   Body：`{ username, email, password, code }`  
   - 校验验证码（purpose=`register`，且 payload 中 username 与请求一致）  
   - 再次校验占用 → 建用户（已验证）→ 返回 access + refresh（与现登录一致）

### 忘记密码

1. `POST /auth/email/send-code` — `{ email, purpose: "reset_password" }`  
   - 邮箱不存在时仍返回成功文案（防枚举）；不发信或静默跳过。
2. `POST /auth/password/reset` — `{ email, code, new_password }` → 改密成功。

### 已登录改密

1. `POST /auth/email/send-code` — `{ purpose: "change_password" }`（需登录；邮箱取当前用户，忽略客户端伪造邮箱）。
2. `POST /auth/me/password` — `{ code, new_password }`（需登录）→ 改密。

### 安全约定（模型层）

- 6 位数字码；仅存哈希；单条最多 5 次错误尝试。
- 新发码使同 `email + purpose` 下未消费旧码全部作废。
- 开发环境无 `RESEND_API_KEY` 或显式 `EMAIL_DEV_LOG_CODES`：可将明文码打到日志；生产禁止。

---

## §2 Resend 配置与前端

### 环境变量

| 变量 | 说明 |
|------|------|
| `RESEND_API_KEY` | Resend API Key（生产必填） |
| `EMAIL_FROM` | 发件人，如 `PulseForge <noreply@yourdomain.com>`（域名须在 Resend 验证） |
| `EMAIL_CODE_TTL_SECONDS` | 默认 `600` |
| `EMAIL_CODE_RESEND_COOLDOWN_SECONDS` | 默认 `60` |
| `EMAIL_CODE_MAX_ATTEMPTS` | 默认 `5` |
| `EMAIL_CODE_DAILY_LIMIT_PER_EMAIL` | 默认 `10` |
| `EMAIL_DEV_LOG_CODES` | 仅 development：无 Key 或显式开启时日志打码 |

发信：HTTP 调用 Resend `emails.send`。邮件正文简短中英双语（产品名、6 位码、用途、过期说明）。  
未配置 Key 且非开发可用模式 → 发码接口返回明确可操作错误，不抛内部堆栈。

部署：HF Space Secrets / 本地 `.env` 增加上述变量；文档说明需在 Resend 验证发件域名。

### 前端

1. **`Signup`**：同页两步  
   - 步骤 1：用户名 / 邮箱 / 密码 →「发送验证码」  
   - 步骤 2：输入验证码 →「注册」（`register` 带 `code`）  
   - 重发倒计时对齐后端 cooldown
2. **`Login`**：增加「忘记密码？」→ `/forgot-password`
3. **新页 `ForgotPassword`**：邮箱 → 发码 → 验证码 + 新密码 → 成功跳转登录
4. **已登录改密**：侧栏用户菜单或设置区轻量「修改密码」弹窗/小页：发码到当前邮箱 → 验证码 + 新密码  
   - 管理员 `UserManagement` 改**他人**密码：保持现状（不发邮件）
5. **i18n**：中英补齐发码、倒计时、错误、防枚举成功提示等
6. **`auth.ts` / axios**：新增 `sendEmailCode`、`resetPassword`、`changeMyPassword`；401 拦截白名单包含发码 / 重置等公开接口，避免误跳登录

---

## §3 错误处理、限流与测试

### 对外错误行为

| 场景 | 行为 |
|------|------|
| 验证码错误 / 过期 / 已用 / 超次 | 统一模糊提示（如「验证码无效或已过期」） |
| 注册发码时 username/email 已占用 | 明确错误（用户本意注册） |
| 忘记密码邮箱不存在 | 仍返回成功：「若该邮箱已注册，将收到验证码」 |
| Resend 失败 / 生产未配置 Key | 「邮件暂时无法发送」类可操作错误 |
| 改密未登录 | 401 |
| 公开注册关闭 | `purpose=register` 发码与 `register` 均 403 |
| 冷却期内重发 | 429，尽量带 `retry_after` |

### 限流与安全

- 同一 `email + purpose`：冷却期内拒绝重发。
- 同一邮箱每日发码上限（默认 10）。
- 可选：按 IP 粗限流（实现时与现有中间件能力对齐，有则加、无则邮箱限流为主）。
- 校验失败累计至上限则作废，需重新发码。
- 日志默认不记明文码（仅开发例外）。
- 改密 / 重置成功后：前端清本地 token 并要求重新登录（重置密码）或保持会话（登录态改密可保持）；**首版不做**完整 refresh 服务端吊销，除非现有设施已具备。

### 测试要点

1. 单元：哈希、过期、attempts、consume、冷却、日限额。
2. API：注册完整流；忘记密码；登录态改密；防枚举；429；模糊错误文案。
3. Mock Resend：不真实发信；断言 to / from / 正文含码。
4. 迁移：存量 `email_verified_at` 非空，可直接登录。
5. 前端：Signup 两步、ForgotPassword、改密 UI、倒计时、i18n。
6. 配置：production 无 Key → 发码失败；development + 日志码 → 本地可走通。

### 首版明确不做

- Magic link
- 改绑邮箱验证流
- 短信 OTP
- 管理员改他人密码发邮件
- 完整 refresh token 服务端吊销（无现成机制则不做）
- SMTP 发信适配器（仅 Resend）

---

## 组件边界（实现时）

| 单元 | 职责 | 依赖 |
|------|------|------|
| `email_sender`（Resend） | 发信；开发日志回退 | settings |
| `email_code_service` | 生成/哈希/校验/限流/作废 | DB、sender |
| `auth_routes` 扩展 | 发码、注册带码、重置、改密 | code_service、auth_service |
| 前端 auth 页与 API | 两步注册、忘记密码、改密 UI | 新 API |

---

## 成功标准

- 无有效验证码无法公开注册出新用户。
- 已知邮箱可完成忘记密码并登录。
- 已登录用户可仅凭邮箱码改密。
- 存量用户不受影响。
- 生产配置 Resend 后真实收信；本地可用开发日志码完成联调。
- 自动化测试覆盖核心服务与关键 API（Mock 发信）。
