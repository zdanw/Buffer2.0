# 用户数据隔离设计（第一期）

**日期：** 2026-08-19  
**状态：** 已定稿（待实现）  
**背景：** 系统将对外开放注册；当前为多用户 JWT 登录，但业务数据全局共享，任意登录用户可读写全库。生产库托管在 Supabase Postgres，曾出现 `rls_disabled_in_public`（表未开 RLS，Data API / anon 可直连读写）安全告警。

## 目标

- 每个注册账号的业务数据相互隔离（一人一套）。
- 表结构预留 `workspace_id`，便于后续引入团队/工作区，第一期不实现团队。
- 图像供应商与 Buffer 账号由每个用户自备，不做平台默认共享。
- **一并堵住 Supabase Data API 公网洞**：对所有应用 `public` 业务表 `ENABLE ROW LEVEL SECURITY`，且不为 `anon` / `authenticated` 建允许策略；该步骤以 **可版本化 Alembic 迁移** 落地，部署时随 `auto_migrate` 自动执行。

## 现状摘要

- 认证：JWT（access + refresh）；公开注册由 `allow_public_signup` 控制。**不使用** Supabase Auth；前端**不**直连 Supabase（无 `@supabase/supabase-js`）。
- 后端：SQLAlchemy + `DATABASE_URL`（Postgres Session，通常为高权限角色）直连；业务鉴权在应用层。
- 业务表（品牌、产品、任务、发布、生成、供应商、Buffer 等）**无** `owner_user_id`；API 仅要求登录，查询不过滤用户。
- CDN 上传走统一 GitHub `images/` 目录；第一期**不改**路径。
- 相关代码对照（本设计不改代码，仅作锚点）：
  - 认证：`backend/bebcare/api/auth_routes.py`、`backend/bebcare/services/auth_dependency.py`
  - 模型 / 路由：`backend/bebcare/models/*`、`backend/bebcare/api/*_routes.py`
  - 库连接 / 迁移启动：`backend/bebcare/database.py`、`backend/migrations/`
  - 上传：`backend/bebcare/utils/github_uploader.py`

## 方案选择

采用 **方案 1 + Supabase RLS 锁死**（安全洞与产品隔离同一迭代）：

1. 业务表与配置表增加必填 `owner_user_id` + 可空 `workspace_id`；列表/读写统一按当前用户过滤。
2. 所有应用 `public` 业务表开启 RLS，**不**为 PostgREST 的 `anon` / `authenticated` 添加允许策略（无策略 = 默认拒绝 Data API）。
3. 后端 `DATABASE_URL` 高权限连接继续绕过 RLS，应用隔离仍靠 `owner_user_id` 过滤——**不以** `auth.uid()` 写 RLS 策略（与当前架构不一致）。

未采用：第一期就建真实 `workspaces` 成员模型（YAGNI）；仅靠应用层包装而不改表；仅为每张表写 Supabase Auth 式 RLS 策略（前端并不直连）。

---

## §1 数据模型与归属

### 核心字段

| 字段 | 规则 |
|------|------|
| `owner_user_id` | **必填**，FK → `users`。每条需隔离的行都有明确主人。 |
| `workspace_id` | **可空**。第一期创建时恒为 `NULL`（个人默认空间）。不建 `workspaces` / 成员表。 |

### 加列范围

**始终按用户隔离（创建时写入当前用户）：**

- `brands`
- `products`（`product_images` 经 product / brand 归属过滤，第一期可不冗余 `owner_user_id`）
- `scheduled_tasks`、`task_executions`、`manual_task_drafts`
- `publish_records`、`generate_tasks`
- 与用户/产品绑定的 prompt 定制数据：随产品归属；若存在全局系统模板，保持只读全员可用（实现时按现表拆清）

**供应商 / Buffer（必填 owner，无平台共享）：**

- `image_provider_configs.owner_user_id`：**必填**
- `buffer_accounts.owner_user_id`：**必填**
- **不加** `is_platform_shared`；不做「平台默认供应商 / 共享 Buffer」
- 列表与读写仅本人可见、可改

### 迁移归属

- 现有全部业务行 + 现有供应商 / Buffer → `owner_user_id = 当前管理员`（`is_admin=True`；若多个取最早创建的一个）
- 管理员继续使用迁移后的 Key / Buffer；新注册用户从空配置开始，自行添加

### 第一期明确不做

- 真实 `workspaces` / 邀请成员
- 管理员伪装 / 代管（仅预留产品方向：后续显式 `acting_as_user_id` + 审计日志）
- CDN 路径按用户分目录
- 改 Chroma collection 命名（仍按 `product_id`；产品已按用户隔离即可）
- 平台默认 / 共享图像供应商或 Buffer
- 基于 Supabase Auth `auth.uid()` 的 per-row RLS 策略（应用隔离在后端完成）

---

## §2 API 过滤与安全边界

### 原则

1. 鉴权仍用现有 JWT；业务查询一律 `owner_user_id == 当前用户`。
2. 跨用户资源一律当不存在：详情 / 更新 / 删除找不到「属于自己」的行 → **404**（不用 403，避免探测他人 ID）。
3. 写操作服务端盖章：创建时写入 `owner_user_id = 当前用户`，`workspace_id = NULL`；**忽略**客户端传入的 owner / workspace。
4. 第一期过滤条件为「属于我」即可，不按 `workspace_id` 分支。
5. Supabase Data API：靠 RLS 启用且无公开策略锁死；**不替代**应用层 owned 过滤。

### 统一访问辅助（建议）

避免每个路由手写漏滤：

- `owned_query(Model, user)` → `filter(owner_user_id=user.user_id)`
- `get_owned_or_404(Model, id, user)`
- 创建：`obj.owner_user_id = current_user.user_id`；`workspace_id = None`

后台任务（定时任务、异步生成）执行时，使用**任务所属用户**的供应商 / Buffer，不得回落到「全局第一份配置」。

### 各 API 行为

| 区域 | 列表 | 读 / 改 / 删 | 创建 |
|------|------|--------------|------|
| 品牌 / 产品 / 任务 / 草稿 / 发布 / 生成 | 仅本人 | 仅本人，否则 404 | 自动归属当前用户 |
| 图像供应商 / Buffer | 仅本人 | 仅本人；**取消「仅管理员可写」的全局模型**，改为主人可写；管理员仍管用户账号等平台能力 | 归属当前用户 |
| 用户管理 `/auth/users` | 仍仅管理员 | 不变 | 不变 |
| Prompt 维度等 | 全局模板：只读全员可用；用户/产品绑定：随产品 owner 过滤 | | |

### 引用完整性（防串号）

创建 / 更新若引用其他实体（任务绑品牌、产品绑 Buffer、生成用某 provider 等）：

- 被引用行也必须 `owner_user_id == 当前用户`
- 否则 404（与「资源不可见」一致；实现时与错误表约定写死，见 §3）

### 管理员边界（第一期）

- 管理员**不能**默认看到他人业务数据（与普通用户同一套 owned 过滤）
- 管理员**可以**：用户 CRUD、系统设置类（若有）、自己名下的业务与 Key / Buffer（含迁移存量）
- **预留**：后续伪装 / 代管；第一期不实现、不暴露 API

### 前端

- 列表接口已按用户过滤，一般无需大改查询逻辑
- 新用户空状态：无品牌 / 无供应商 / 无 Buffer 时给出引导（配置 Key → 配 Buffer → 建品牌）
- 去掉「只有管理员才能改图像供应商」这类 UI 假设（改为登录用户管理自己的）

---

## §3 数据流 / 迁移 / 错误处理与测试范围

### 数据流

```
注册/登录 → JWT(user_id)
    ↓
任意业务 API
    ↓
解析当前用户 → owned 过滤 / 创建盖章
    ↓
读：仅 owner_user_id = 我
写：新行 owner=我, workspace_id=NULL
引用校验：brand / product / provider / buffer 等同属我
    ↓
异步生成 / 定时任务
    ↓
用「任务所属用户」的 provider / buffer，不落全局默认

并行（库层）：
Data API (anon/authenticated) → RLS ON + 无允许策略 → 拒绝
后端 DATABASE_URL → 高权限角色 → 不受 RLS 阻拦 → 仍靠应用层隔离
```

| 场景 | 行为 |
|------|------|
| Studio 生成图 | 选用的 `image_provider` 必须属于当前用户；生成任务写入 `owner_user_id` |
| 定时 / 手动任务 | 任务及其关联品牌、产品、Buffer 均属同一用户；执行时按任务 owner 取凭证 |
| 发布到 Buffer | 只用该用户自己的 `buffer_accounts` |
| 新产品空账号 | 无品牌 / 无 Key / 无 Buffer 时允许登录；业务操作用明确错误引导配置 |

### 迁移步骤（Alembic；部署时自动执行）

建议拆成可审阅的迁移（可同一次发布内连续 upgrade），逻辑顺序如下：

1. **Owner 列（可空）**：各目标表增加 `owner_user_id`（可空）+ `workspace_id`（可空）
2. **回填**：定位种子管理员，现有行全部 `UPDATE ... SET owner_user_id = <admin>`
3. **收紧**：`owner_user_id` 改为 **NOT NULL**，加 FK 与索引（至少 `(owner_user_id)`）
4. **RLS 锁死（版本化）**：对所有应用 `public` 业务表执行 `ENABLE ROW LEVEL SECURITY`（见 §4）；**不** `CREATE POLICY` 给 `anon` / `authenticated`
5. **应用层**：上线 owned 过滤；供应商 / Buffer 写权限改为主人可写
6. **回滚**：
   - Owner 列迁移可逆（删列）；**数据归属无法自动还原为「全局共享」语义**，上线前备份 DB
   - RLS 迁移 `downgrade`：`DISABLE ROW LEVEL SECURITY`（仅应急；生产勿轻易回滚到「无 RLS」）

存量文件 / CDN URL **不搬迁**。

### 错误处理

| 情况 | HTTP | 说明 |
|------|------|------|
| 资源不存在或不属于我 | **404** | 统一「当不存在」，防 ID 探测 |
| 引用了他人的 brand / provider / buffer | **404** | 与资源不可见一致 |
| 未配置 provider / buffer 却发起生成或发布 | **400** | 明确提示去设置页配置 |
| 未登录 / token 无效 | **401** | 保持现有 |
| 非管理员访问用户管理 | **403** | 仅平台管理接口 |

客户端传入的 `owner_user_id` / `workspace_id`：schema 不暴露或服务端静默忽略。

### 测试范围（第一期必过）

**隔离（核心）**

- A 不能 list / get / patch / delete B 的：品牌、产品、任务、草稿、发布、生成任务、图像供应商、Buffer
- A 不能用 B 的 UUID 挂引用（任务→品牌、生成→provider 等）
- 管理员不能 list 到 B 的业务数据（除非 owner 是管理员自己）

**归属与迁移**

- 迁移后存量行 `owner_user_id` = 管理员且非空
- 新注册用户创建的数据 owner 为自己；列表初始为空

**执行路径**

- 异步生成 / 定时任务使用任务 owner 的凭证，不串用他人 Key

**Supabase / RLS**

- 迁移后目标表 `relrowsecurity = true`
- 使用 anon key 调用 PostgREST 读任意业务表应失败（无权限 / 空拒绝），验证 Data API 已锁死
- 后端经 `DATABASE_URL` 的冒烟（登录、列表、创建）仍通过

**回归**

- 管理员用户 CRUD 仍可用
- 登录、刷新 token、公开注册行为不变（除非另改产品策略）

**明确不测（第一期）**

- 工作区邀请、伪装代管、CDN 分目录、平台共享供应商
- 基于 `auth.uid()` 的行级策略正确性（本设计不实现该类策略）

---

## §4 Supabase RLS 锁死（版本化 Alembic）

### 为何与 owner 隔离同迭代

- Owner 隔离解决：**登录用户之间**经应用 API 的串数据问题。
- RLS 锁死解决：**任何人持有项目 URL + anon key** 经 Data API 绕过应用直连库的问题。
- 二者互补；仅做其一仍有另一面暴露。

### 策略（第一期）

| 项 | 决定 |
|----|------|
| 范围 | **所有应用业务表**（`public` schema 下由本系统管理的表，含 `users`；**排除** `alembic_version`）一律 `ENABLE ROW LEVEL SECURITY` |
| 策略 | **不创建**面向 `anon` / `authenticated` 的允许策略（无策略 = PostgREST 拒访） |
| 后端 | 继续用 Session `DATABASE_URL`；依赖表所有者 / 高权限角色绕过 RLS |
| 不做 | 不按 `owner_user_id` / `auth.uid()` 写 RLS 策略；不把隔离逻辑下沉到 Supabase Auth |

### Alembic 实现要点

- 新增迁移（建议独立 revision，便于单独回滚 RLS）：在 `upgrade()` 中对表清单循环 `ALTER TABLE ... ENABLE ROW LEVEL SECURITY`。
- 表清单：以当前 `Base.metadata` / 已知业务表名为准，实现时列全并与 Advisors 告警表对齐；新建表的后续迁移若引入新表，须同步 `ENABLE RLS`（或约定「建表迁移末尾必开 RLS」）。
- 方言：仅在 PostgreSQL 执行；SQLite 本地开发 **跳过** RLS（`if bind.dialect.name == "postgresql"`）。
- `downgrade()`：对应表 `DISABLE ROW LEVEL SECURITY`。
- 部署：生产 `auto_migrate=True` 时随应用启动自动 upgrade（现有 `init_db` 路径），无需手点 Dashboard（Dashboard 仅作上线后 Advisors 复核）。

### 运维补充（非迁移代码，上线清单）

- 上线后在 Supabase **Advisors** 确认 `rls_disabled_in_public` 消失。
- 确认 **service_role** 未暴露到前端；若 anon key 曾泄露则轮换。
- 大变更前备份生产库。

---

## 成功标准

1. 任意两个普通用户之间业务数据互不可见、不可引用。
2. 供应商与 Buffer 仅主人可读写；无全局共享配置。
3. 存量数据归属管理员后，管理员工作流不中断。
4. 表上存在可空 `workspace_id`，为后续团队功能留口，第一期恒为 `NULL`。
5. 所有应用 `public` 业务表已 `ENABLE ROW LEVEL SECURITY`，且以 Alembic 版本管理；Supabase Advisors 不再报「表因未开 RLS 而公开可访问」；anon Data API 无法读写业务表；后端 API 冒烟正常。

## 后续（非第一期）

- 引入 `workspaces` + 成员关系；业务过滤改为按 workspace 权限解析。
- 管理员显式伪装 / 代管 + 审计日志。
- CDN / 对象存储按用户（或 workspace）分前缀。
- 若未来前端改为直连 Supabase：再为 Data API 设计与 `owner_user_id` 对齐的 RLS 策略（届时需统一身份模型）。
