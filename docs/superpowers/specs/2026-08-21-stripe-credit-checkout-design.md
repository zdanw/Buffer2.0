# Stripe 沙盒：平台出图次数包 Checkout 设计

**日期：** 2026-08-21  
**状态：** 已定稿（用户确认后写执行计划）  
**背景：** Credit Grants 已上线（试用 + admin 发放）；购买弹窗仍为「联系管理员」。本期接入 Stripe **测试模式** Hosted Checkout，支付成功后自动发 grant。

## 已确认产品决策

| 项 | 决定 |
|----|------|
| 商品形态 | 一次性次数包（非订阅） |
| SKU | 环境变量 / Stripe Dashboard 配置；代码不硬编码价格与档位 |
| 结账 | Stripe Hosted Checkout Session |
| 目录 | 后端配置映射 → `GET /billing/credit-packs`；下单只传 `price_id` |
| 人工入口 | 移除联系管理员 CTA；无 Stripe 配置时购买按钮不可用 |
| 会话落库 | 方案 2：`stripe_checkout_sessions` 表（pending → paid） |

## 目标

- 登录用户可选配置中的次数包 → 跳转 Stripe Checkout（test）→ 支付成功回站。
- Webhook `checkout.session.completed` 验签后将本地会话标为 `paid`，并 `create_grant(source=stripe)`。
- 幂等：重复 webhook 不重复发次数。
- 沙盒密钥与 webhook secret 全部来自环境变量。

## 明确不做

- 正式/live 模式切换逻辑以外的生产对账工具
- 订阅、退款自动扣回次数、Customer Portal
- 微信支付
- 站内 Payment Element
- 改动出图预扣 / BYOK 语义

## 架构

```
前端 SubscribeCreditsModal
  → GET /billing/credit-packs
  → POST /billing/checkout-session { price_id }
       → 插入 stripe_checkout_sessions(pending)
       → Stripe Checkout Session（metadata: user_id, local_id, credits）
       → 返回 { url }
  → window.location = url

Stripe → POST /billing/webhook（原始 body + Stripe-Signature）
  → 验签
  → 会话 paid + create_grant(external_ref=stripe_session_id)
  → 幂等：已 paid 直接 200
```

成功/取消回跳：`{FRONTEND_BASE_URL}/studio?checkout=success|cancel`；前端刷新 `/auth/me` 额度。

## 配置

| 环境变量 | 含义 |
|----------|------|
| `STRIPE_SECRET_KEY` | 测试密钥 `sk_test_...`；空则 billing 关闭 |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` |
| `STRIPE_CREDIT_PACKS` | JSON 数组：`[{"price_id":"price_...","credits":20,"label":"20 credits"}]` |
| `FRONTEND_BASE_URL` | Checkout success/cancel 回跳根（如 `http://localhost:5174`） |

`stripe_enabled` = 有 secret key 且 packs 解析后非空。

## 表 `stripe_checkout_sessions`

| 字段 | 含义 |
|------|------|
| `id` | 本地 UUID PK |
| `user_id` | FK → users |
| `stripe_session_id` | Stripe Checkout Session id，创建后写入，唯一 |
| `price_id` | 下单时的 Stripe price |
| `credits` | 应付次数（来自配置，写入 metadata 防篡改） |
| `status` | `pending` \| `paid` \| `expired` |
| `grant_id` | 发放后的 grant id，可空 |
| `created_at` / `updated_at` | |

发放：`create_grant(..., source="stripe", quantity=credits, external_ref=stripe_session_id)`。  
`image_credit_grants.external_ref` 对 `source=stripe` 建议唯一（防双发）。

## API

| 方法 | 路径 | 鉴权 | 说明 |
|------|------|------|------|
| GET | `/v1/billing/credit-packs` | 登录 | `{ enabled, packs:[{price_id,credits,label}] }` |
| POST | `/v1/billing/checkout-session` | 登录 | body `{price_id}` → `{ url, session_id }`；未启用 503 |
| POST | `/v1/billing/webhook` | Stripe 签名 | 原始 body；无 JWT |

Admin `credit-grants` API 保留（运营补发），UI 不再引导「联系购买」。

## 前端

- 重写 `SubscribeCreditsModal`：拉 packs → 选档 → Checkout；`enabled=false` 时按钮禁用并说明。
- 去掉 `billingContact` / 联系 CTA。
- Studio 回站 `?checkout=success` 时刷新额度并提示。

## 测试

- Packs 解析与 `enabled` 单元测试。
- Checkout：mock Stripe，断言落库 pending + 返回 url。
- Webhook：mock 验签事件，断言 grant + 幂等二次调用。
- 未配置密钥时 checkout 503、packs `enabled=false`。
