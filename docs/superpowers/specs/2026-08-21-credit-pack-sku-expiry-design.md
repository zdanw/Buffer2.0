# 计费 SKU 调整 + Stripe 次数包 30 天过期（方案 2）

**日期：** 2026-08-21  
**状态：** 已定稿（已实现）  
**背景：** Stripe 一次性 Checkout 已落地；现有 SKU 为单档（如 20 credits），文案写「不按月重置」。产品改为三档 Basic / Pro / Super，且 **Stripe 购买的点数自发放起 30 天后过期清零**。

**前置设计：**
- [`2026-08-20-image-credit-grants-design.md`](./2026-08-20-image-credit-grants-design.md)
- [`2026-08-21-stripe-credit-checkout-design.md`](./2026-08-21-stripe-credit-checkout-design.md)

## 已确认产品决策

| 项 | 决定 |
|----|------|
| 结账形态 | 仍为 **一次性** Stripe Checkout（非订阅自动续费） |
| SKU | Basic **30** 点 · Pro **120** 点 · Super **300** 点 |
| 标价（USD） | $3.99 / $9.99 / $19.99 — **仅在 Stripe Dashboard 建价**；代码不硬编码金额 |
| 过期 | Stripe grant：`expires_at = 发放时刻(UTC) + 30 天`；到期未用完作废 |
| 试用 / 管理员发放 | `expires_at = NULL`，不过期 |
| 过期实现 | **方案 2**：`expires_at` + 读路径懒排除 + **定时清零任务** |
| 扣点顺序 | 改为 **FEFO**：先扣 `expires_at` 更早的 active grant；同到期日再按 `created_at` |
| 叠加 | 多包可并存；各包独立计时 |

## 目标

- 运营在 Stripe 建三档 Price，经 `STRIPE_CREDIT_PACKS` 映射后，购买弹窗展示 Basic / Pro / Super。
- 支付成功发放的 stripe grant 带 30 天有效期；余额与预扣均不计过期包。
- 定时任务将已过期且仍有剩余的 grant 清零并标为 `expired`，保证账本最终一致。
- 前端文案改为「购买后 30 天内有效」，去掉「不按月重置 / 买多少用多少」。

## 明确不做

- Stripe Subscription / Customer Portal / 自动续费
- 退款自动扣回次数
- 试用或 admin grant 默认 30 天过期（本期不改）
- 硬编码 price_id 或美元金额进仓库
- 改动 BYOK / 预扣 TTL / 出图计次范围

## 架构

```
Stripe Checkout 成功
  → create_grant(source=stripe, …, expires_at=now+30d)

余额 / 预扣
  → 仅 status=active 且 (expires_at IS NULL OR expires_at > now)
  → 预扣排序：expires_at ASC NULLS LAST, created_at ASC

定时任务 expire_grants（建议每小时）
  → 找出 expires_at <= now 且 status=active 且 remaining > 0
  → remaining=0, status=expired
```

## §1 数据模型

### 1.1 `image_credit_grants` 新增列

| 字段 | 类型 | 含义 |
|------|------|------|
| `expires_at` | `DateTime`，可空 | 过期时刻（UTC）；`NULL` = 永不过期 |

### 1.2 `status` 扩展

| 值 | 含义 |
|----|------|
| `active` | 可计入余额（仍须满足未过期） |
| `exhausted` | 用尽 |
| `revoked` | 人工撤销 |
| `expired` | 定时任务（或显式过期路径）清零后的终态 |

迁移：Alembic 加列即可；既有行 `expires_at=NULL`。

## §2 Grant 服务语义

### 2.1 `create_grant`

新增可选参数 `expires_at: datetime | None = None`。  
Stripe fulfill（`stripe_billing_service`）在调用时传入 `datetime.utcnow() + timedelta(days=30)`。  
天数可用设置项 `image_credit_stripe_expiry_days: int = 30`（env `IMAGE_CREDIT_STRIPE_EXPIRY_DAYS`），避免魔法数散落。

### 2.2 `remaining_credits`

过滤条件增加：

- `status == active`
- `expires_at IS NULL OR expires_at > utcnow()`

读路径**不强制**写库；定时任务负责落 `expired`。

### 2.3 `reserve_one`（FEFO）

候选 grant：`active`、`remaining > 0`、未过期。  
排序：`expires_at ASC NULLS LAST`，再 `created_at ASC`。  
（SQLite / Postgres 均需可测；SQLite 对 NULLS LAST 可用 `CASE`/`IS NULL` 兼容写法。）

### 2.4 `expire_due_grants(db) -> int`

- 查询：`status=active` 且 `expires_at IS NOT NULL` 且 `expires_at <= utcnow()`
- 对每条：`remaining=0`，`status=expired`，更新 `updated_at`
- 返回处理条数  
- **幂等**：已 `expired` 的不再匹配

有未 confirm 的 reservation 挂在即将过期 grant 上时：定时清零仍执行；进行中的预扣依赖既有 stale reclaim / confirm 路径。本期不额外阻塞过期（YAGNI）。

## §3 定时任务

| 项 | 决定 |
|----|------|
| 入口 | 在现有 APScheduler（`scheduler_service.start()` 之后）注册固定 interval job |
| 周期 | 默认 **1 小时**（可设 `IMAGE_CREDIT_EXPIRE_INTERVAL_MINUTES`，默认 60） |
| 启动 | `startup` 时先跑一次 `expire_due_grants`（与现有 `reclaim_stale_reservations` 并列） |
| 实现 | `credit_grant_service.expire_due_grants`；scheduler 内开短生命周期 Session，commit/rollback |
| 多实例 | `max_instances=1`；接受「多副本可能各跑一次」的幂等清零 |

## §4 配置与 Stripe 运营

### 4.1 `STRIPE_CREDIT_PACKS`（示例，price_id 由运营填入）

```json
[
  {"price_id":"price_…","credits":30,"label":"Basic — 30 credits"},
  {"price_id":"price_…","credits":120,"label":"Pro — 120 credits"},
  {"price_id":"price_…","credits":300,"label":"Super — 300 credits"}
]
```

### 4.2 Stripe Dashboard（测试/正式各一套）

| SKU | 类型 | 单价 |
|-----|------|------|
| Basic | one-time | USD 3.99 |
| Pro | one-time | USD 9.99 |
| Super | one-time | USD 19.99 |

代码与文档只描述映射；**不把真实 price_id 提交进 git**（`.env` / 部署密钥管理）。

### 4.3 新增 settings（可选但推荐）

| 环境变量 | 默认 | 含义 |
|----------|------|------|
| `IMAGE_CREDIT_STRIPE_EXPIRY_DAYS` | `30` | Stripe grant 有效天数 |
| `IMAGE_CREDIT_EXPIRE_INTERVAL_MINUTES` | `60` | 清零任务间隔 |

## §5 API / 前端

- `GET /billing/credit-packs`：仍返回配置中的 `price_id` / `credits` / `label`；无需返回金额（金额在 Stripe Checkout 页展示）。
- `/auth/me` 的 `image_credits_remaining`：走更新后的 `remaining_credits`（自动排除过期）。
- i18n（中英）：
  - 去掉「次数包不按月重置…」
  - 改为明确 **购买后 30 天内有效，过期未用完作废**
- 购买弹窗按钮文案可继续用 label + credits；不必在 UI 硬编码美元价。

Admin `credit-grants` 列表：响应中增加 `expires_at`（可空），便于运营核对；无强制改 UI。

## §6 测试

- 单元：`create_grant` 带/不带 `expires_at`；`remaining_credits` 排除过期；`reserve_one` FEFO；`expire_due_grants` 幂等。
- 服务：Stripe fulfill 后 grant 的 `expires_at` 约等于 now+30d（可 freeze 时间）。
- 回归：试用 / admin grant 仍无过期、余额逻辑不变。
- 同步：改 `backend/` 后跑 `scripts/sync_deploy_copies.py`（或等价镜像 `hf-space/`）。

## §7 成功标准

1. 配置三档 packs 后，弹窗可见 Basic / Pro / Super，且 credits 为 30 / 120 / 300。  
2. 测试卡支付成功后余额增加，且该 grant 有 `expires_at`。  
3. 将某 grant 的 `expires_at` 拨到过去：余额立即不计；跑 `expire_due_grants` 后 status=`expired`、remaining=0。  
4. 试用额度不受 30 天规则影响。

## 风险与备注

- 过期窗口内（任务未跑到）读路径已不计余额，用户体验正确；定时任务保证状态字段最终一致。  
- 多包 FEFO 改变了原 FIFO；已购未过期包的扣减顺序可能变化，属预期。  
- 标价以 Stripe 为准；若 Dashboard 价与产品表不一致，以 Stripe Checkout 展示为准。
