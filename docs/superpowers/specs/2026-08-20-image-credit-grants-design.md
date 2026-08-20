# 平台出图次数包设计（方案 2：Credit Grants）

**日期：** 2026-08-20  
**状态：** 已定稿（待实现）  
**背景：** Studio 当前强制用户自备图像 API Key（BYOK）；文案走平台 `DEEPSEEK_*`。产品需要「可用平台图像模型、少量免费次数、用完后买次数包或自配 Key」的付费路径。支付第一期人工开通，接口预留 Stripe / 微信。

## 目标

- 用户可选择使用 **系统（平台）图像 Provider** 出图，按 **次数包（Grant）** 计费。
- **仅平台 Key 出图**计次；文案继续免费用平台 DeepSeek；BYOK 出图不计次。
- 注册赠送少量试用次数（默认 2）；用尽后须 admin 发放次数包，或自行配置图像供应商。
- **预扣 + 失败退回**，防止并发超用。
- Studio 显式选择：`平台额度（剩余 n）` vs `我的供应商`。
- 支付后补：同一 `create_grant` 服务，换 `source` + `external_ref` 即可。

## 现状摘要

- 图像：`ImageProviderConfig` + `OwnedMixin`；`resolve_image_provider` 只解析当前用户自有配置；无平台共享池。
- 文案 / Vision：环境变量 `DEEPSEEK_*` / `VISION_*`，全员共用、无配额。
- 生成：`POST /generate/`、`/generate/image/` 经 `_require_image_provider` 门禁；`/generate/copywriting/` 不要求图像供应商。
- Studio：`ImageModelPicker` 在无自有 provider 时显示「尚未添加…」；生成按钮不检查额度。
- **无** Stripe / 订阅 / 配额 / 用量账本。
- 相关锚点：
  - `backend/bebcare/providers/registry.py`（`resolve_image_provider`）
  - `backend/bebcare/api/generate_routes.py`（`_require_image_provider`）
  - `backend/bebcare/models/generate_task.py`、`image_provider.py`、`user.py`
  - `frontend/src/components/ImageModelPicker.tsx`、`pages/Studio.tsx`
  - `frontend/src/pages/ImageProviderSettings.tsx`、用户管理页

## 方案选择

采用 **方案 2：完整 Credit Grant 模型**（非单一余额字段、非按 `GenerateTask` 倒推）。

- 每一笔试用 / 人工发放 / 未来支付 = 一条 `image_credit_grants`。
- 消费 FIFO：预扣最早的 `active` 且 `remaining > 0` 的 grant。
- 预扣落在 `image_credit_reservations`，与 `GenerateTask` 关联；成功 confirm，失败 refund。

未采用：方案 1（仅 `User.balance`）——扩展支付 SKU / 审计较弱；方案 3（统计任务倒推）——无法干净表达次数包与预扣。

**与既有隔离设计的关系：** `2026-08-19-user-data-isolation-design.md` 曾规定「不做平台默认共享图像供应商」。本设计在该约束上增加**唯一例外**：`is_system=true` 的系统 Provider 仅供 `image_provider_mode=platform` 且有额度时使用；用户自有 BYOK 隔离规则不变。

### 产品约束（已确认）

| 项 | 决定 |
|----|------|
| 计次范围 | 仅平台 Key 出图 |
| 支付 | 先 admin 人工发放；预留 Stripe / 微信 |
| 平台模型来源 | 独立 System Provider（`is_system`），不绑某 admin 个人账号 |
| 订阅形态 | 次数包，不按自然月重置 |
| 扣次 | 发起时预扣，失败自动退回 |
| Studio 默认 | 显式二选一：平台额度 vs 我的供应商 |

---

## §1 数据模型与额度语义

### 1.1 扩展 `image_provider_configs`

| 字段 | 规则 |
|------|------|
| `is_system` | `bool`，默认 `false`。系统行仅 admin CRUD；不出现在普通用户 `listImageProviders`。 |
| `owner_user_id` | 系统行允许 `NULL`（推荐），或内部占位但不按「个人配置」暴露。 |

- 全站建议维护 **一个** 默认系统 Provider（`is_system && is_active`，必要时 `is_default`）。
- 用户选「平台额度」时解析该系统 Provider，**不**走用户 owned 查询。

### 1.2 新表 `image_credit_grants`

| 字段 | 含义 |
|------|------|
| `id` | PK |
| `user_id` | FK → users |
| `source` | `signup_trial` \| `admin_grant` \| `stripe` \| `wechat`（后两者第一期仅枚举预留） |
| `quantity` | 本包总张数 |
| `remaining` | 剩余可预扣张数 |
| `status` | `active` \| `exhausted` \| `revoked` |
| `note` | admin 备注，可空 |
| `external_ref` | 支付单号预留，可空 |
| `created_at` / `updated_at` | |

- 注册成功：自动插入一笔 `signup_trial`（`quantity` / `remaining` = 配置值，默认 **2**）。
- Admin「加次数」：插入 `admin_grant`。
- **剩余总次数** = `sum(remaining)` where `status = active`。

### 1.3 新表 `image_credit_reservations`

| 字段 | 含义 |
|------|------|
| `id` | PK |
| `user_id` | FK |
| `generate_task_id` | FK → generate_tasks，建议 1:1 |
| `grant_id` | 本笔预扣来自哪条 grant |
| `amount` | 固定 `1`（一次出图） |
| `status` | `reserved` \| `confirmed` \| `refunded` |
| `created_at` / `updated_at` | |

### 1.4 Admin API（第一期）

- `POST /admin/users/{id}/credit-grants` — body: `{ quantity, note? }`
- `GET /admin/users/{id}/credit-grants` — 列表各包
- 可选：`POST .../credit-grants/{grant_id}/revoke` — 未用完作废；已 `reserved` 不回溯历史任务

稳定服务入口（支付预留）：

```text
CreditGrantService.create_grant(user_id, quantity, source, note?, external_ref?)
```

### 1.5 明确不做（本设计范围外）

- Stripe / 微信收银台与 webhook 实现（只留 `source` + `external_ref` + service）
- 月卡 / 订阅布尔门禁（只认 grant.remaining）
- 文案 / token 计费
- 用户自助购买页（CTA 可为「联系管理员」）

---

## §2 解析门禁与生成流程

### 2.1 请求字段

在现有 `image_provider_id` / `image_model` / `image_size` 上增加：

- `image_provider_mode`: `"platform"` | `"byok"`

| 模式 | 行为 |
|------|------|
| `platform` | 解析 system provider；**必须**预扣 1 次；忽略用户自有 `image_provider_id`（或拒绝混传） |
| `byok` | 现有 `resolve_image_provider(..., owner_user_id=当前用户)`；**不**预扣 |

旧客户端未传 mode 时的兼容默认：有自有 provider → `byok`；否则剩余额度 > 0 → `platform`；否则 400。

### 2.2 统一解析

包装 / 替换 `_require_image_provider`：

1. `byok` → 现有 owned 解析；失败文案保持「未配置图像供应商…」
2. `platform` → `credit_remaining < 1` 则额度错误；否则 `resolve_system_image_provider`
3. 系统未配置 → 运维向错误（与「去配自己的 Key」区分）
4. `assert_owned_ref` **仅** byok 路径使用

### 2.3 出图时序（`/generate/`、`/generate/image/`）

`/generate/copywriting/` **不**进入本流程。

```text
1. 鉴权 + 产品归属
2. 解析 mode → provider + model
3. 创建 GenerateTask（同事务内或紧随其后拿到 task_id）
4. if platform:
     对候选 grant SELECT … FOR UPDATE（FIFO by created_at）
     WHERE remaining >= 1 条件更新 remaining -= 1
     remaining == 0 → status = exhausted
     INSERT reservation(status=reserved, generate_task_id, grant_id, amount=1)
5. BackgroundTasks → ContentGenerator.generate_image_async
6. 终态：
   - SUCCESS → reservation.status = confirmed
   - FAILED / 取消 → reservation = refunded；grant.remaining += 1；必要时 status 改回 active
```

并发：依赖 grant 行锁 + 条件更新；同一用户多请求不会把同一张额度卖两次。

### 2.4 错误语义

| 情况 | HTTP（建议） | 前端引导 |
|------|----------------|----------|
| platform 且额度 0 | 402 Payment Required | 买次数包 / 配置自己的 Key |
| platform 但系统 Provider 未配 | 503 | 联系管理员 |
| byok 未配供应商 | 400 | 现有设置页引导 |
| 出图失败 | 任务 FAILED | 自动退回，可重试 |

### 2.5 调度任务

- `scheduled_tasks` 增加 `image_provider_mode`（及沿用现有 provider/model 字段）。
- 执行路径与 Studio **同一套**解析 + 预扣。
- `platform` 且额度不足 → 本次执行失败并记日志；**禁止**静默改走 BYOK。

---

## §3 Studio / ImageModelPicker UI 与 Admin 开通

### 3.1 前端所需接口数据

`GET /auth/me` 或 `GET /billing/image-credits`：

```ts
image_credits: { remaining: number }
has_system_image_provider: boolean
```

自有列表仍用 `listImageProviders()`，且 **排除** `is_system`。

### 3.2 ImageModelPicker

1. **来源单选**
   - `平台额度（剩余 n）` — `n=0` 或无系统 Provider 时 disabled
   - `我的供应商` — 无配置时展开为空态 + 链到 `/image-models`
2. **随来源切换下游控件**
   - 平台：展示系统模型列表 + 比例；不展示用户 Provider 下拉
   - BYOK：保持现有「服务商 → 模型 → 比例」
3. **黄条三态**（替换单一 `noProviders`）
   - 无额度且无 BYOK → 次数用尽：开通次数包或自配 Key
   - 系统未就绪 → 平台出图暂不可用
   - 选 BYOK 且列表空 → 现有「尚未添加…」
4. 选 platform 时生成区提示：`本次将消耗 1 次平台额度`
5. 默认来源：有额度且系统可用 → `platform`；否则有 BYOK → `byok`

### 3.3 Studio 提交

- 请求携带 `image_provider_mode`；byok 时带 `image_provider_id` / `image_model`。
- 文案-only：不传 mode、不展示扣次。
- 错误 Toast / 内联 CTA 对齐 §2.4。

### 3.4 用户设置页

- 普通用户只管理 BYOK；可加一句说明可在 Studio 用平台额度。
- 列表 API 不返回系统行。

### 3.5 Admin：系统 Provider

- 独立入口「平台图像供应商」（仅 `is_admin`）。
- 复用现有图像供应商表单；API：`/admin/system-image-providers/`（或等价鉴权）。
- 与「我的图像模型」列表隔离。

### 3.6 Admin：发放次数

- 用户管理：展示剩余 n、grant 明细；「发放次数」→ `quantity` + `note`。
- Studio「购买」CTA 第一期可为联系管理员 / 说明文案，不接收银台。

### 3.7 i18n

新增中英键：来源标签、剩余次数、扣次提示、额度用尽、系统未配置、发放成功等；收敛 `imageModelPicker.noProviders` 的误导语义。

---

## §4 边界与测试要点

### 4.1 注册赠送

- 新用户注册成功（邮箱验证通过并创建用户的那一跳，与现有注册流程对齐）→ **恰好一笔** `signup_trial`。
- 幂等：重复回调 / 重试不得发第二笔试用（按 `user_id + source=signup_trial` 唯一，或创建用户事务内只插一次）。
- 默认张数：配置项（如 `IMAGE_CREDIT_SIGNUP_TRIAL=2`），便于改 1/2 而不改代码。
- 历史用户（设计上线前已存在）：迁移时对「尚无任何 `image_credit_grants`」的用户一次性回填一笔 `signup_trial`（数量同配置默认值）。已有 grant 的用户不重复发。

### 4.2 并发与预扣

- 同一用户并行两次 platform 出图、且 `remaining=1`：仅一笔成功预扣，另一笔额度不足。
- 预扣成功后供应商失败：reservation → `refunded`，`remaining` 恢复，用户可再次发起。
- 预扣成功后进程崩溃：任务标记 FAILED 时退回；并增加启动/周期扫描：超过 **15 分钟**仍为 `reserved` 且任务已非进行中的 reservation 自动 refund。
- BYOK 与 platform 并行：BYOK 不改 grant；互不干扰。
- 一笔 grant `remaining` 从 1→0 时 `status=exhausted`；退回后若曾 exhausted 应回到 `active`。

### 4.3 调度（Automation）

- 任务保存的 `image_provider_mode=platform`：执行时预扣；额度为 0 → 执行失败，状态可观测，不改 mode。
- `byok` 调度：不预扣；用户删除了自己的 provider → 与现网一致的失败。
- 与手动 Studio 共用 `CreditGrantService` / 解析函数，禁止调度路径另写一套扣次。

### 4.4 Admin 自己与角色

- **Admin 出图**：与普通用户相同规则（也走 grant / BYOK）。不加「admin 无限平台出图」隐式特权，避免账单黑洞；若运维需要，用 admin 给自己发大额 grant。
- **仅 admin** 可：CRUD 系统 Provider、给任意用户 `create_grant` / revoke。
- 普通用户不能：列出/修改系统 Provider、给自己加 grant、看他人 grant。

### 4.5 其他边界

- 只出文案：零扣次、零 reservation。
- 「文案+图」一次请求：只为图像阶段预扣 1 次（不是 2）。
- Revoke grant：仅减少未预扣的 `remaining`；进行中的 `reserved` 仍按任务终态 confirm/refund。
- 系统 Provider 被禁用 / 删除：已选 platform 的请求失败（503/400），已 reserved 的失败任务须退回额度。

### 4.6 建议测试清单

| # | 场景 | 期望 |
|---|------|------|
| 1 | 新注册用户 | 1 笔 trial，remaining=2（或配置值） |
| 2 | platform 出图成功 | remaining-1，reservation=confirmed |
| 3 | platform 出图失败 | remaining 恢复，reservation=refunded |
| 4 | remaining=0 再 platform | 拒绝；引导 BYOK 或加包 |
| 5 | BYOK 出图 | remaining 不变 |
| 6 | 双请求抢最后 1 次 | 一成一败 |
| 7 | admin 发放 20 | 新 grant，remaining 总和 +20 |
| 8 | 调度 platform 无额度 | 执行失败，不静默 BYOK |
| 9 | 非 admin 调发放 API | 403 |
| 10 | 用户 list providers | 不含 is_system |
| 11 | 仅 copywriting | 无 reservation |
| 12 | 试用幂等 | 不重复发放 |

---

## 实现插入点（摘要）

| 目的 | 位置 |
|------|------|
| 门禁 + 预扣 | `generate_routes`（`_require_image_provider` / generate / generate/image） |
| 解析 | `providers/registry.py`（system 分支） |
| 任务终态退回 | `generate_task` 更新 SUCCESS/FAILED 处 |
| 调度 | `apscheduler_service` 传 mode + 共用服务 |
| UI | `ImageModelPicker`、`Studio`、用户管理、系统 Provider 设置页 |
| i18n | `imageModelPicker.*`、admin grant 文案 |

---

## 成功标准

- 无 BYOK 的新用户可用平台额度完成配置次数内的出图；用尽后无法再走 platform，但配置 BYOK 后仍可出图。
- Admin 可配置系统 Provider，并给用户发放次数包；发放立即反映在 Studio「剩余 n」。
- 失败出图不吞额度；并发不超卖。
- 文案生成行为与计费无关，保持现网。
- 支付未接入前，产品闭环仅依赖 admin 发放 + BYOK。
`}