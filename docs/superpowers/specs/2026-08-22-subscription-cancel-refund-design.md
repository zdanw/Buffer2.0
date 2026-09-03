# 订阅取消与人工退款设计

**日期：** 2026-08-22  
**状态：** 已定稿（方案 1，用户要求直接实现）

## 产品决策

| 项 | 决定 |
|----|------|
| 取消方式 | 用户自助：产品内「取消订阅」 |
| 取消语义 | `cancel_at_period_end=true`；当期继续可用至周期结束，不自动退款 |
| 取消后次数 | 继续可用，直至该笔 grant 30 天过期或用完 |
| 撤回取消 | 周期结束前可「恢复续费」 |
| 退款 | 不自动退；管理员在用户管理对某次 Stripe 发票退款，可勾选是否撤销对应剩余次数 |

## 架构

```
用户 SubscribeCreditsModal
  → GET /billing/subscription
  → POST /billing/subscription/cancel   # cancel_at_period_end
  → POST /billing/subscription/resume

管理员 UserManagement
  → GET /auth/users/{id}/billing/invoices
  → POST /auth/users/{id}/billing/refunds { invoice_id, revoke_credits }

Webhook 增量
  → customer.subscription.updated / deleted → 同步本地 stripe_subscriptions
  → checkout.session.completed → 写入 customer/subscription id
```

## 表 `stripe_subscriptions`

| 字段 | 含义 |
|------|------|
| user_id | FK |
| stripe_customer_id | Stripe Customer |
| stripe_subscription_id | 唯一 |
| price_id | 当前 price |
| status | Stripe status |
| cancel_at_period_end | bool |
| current_period_end | 周期结束 UTC |

Checkout 创建时复用已有 customer（按 user 查本地表，否则 `Customer.create(metadata.user_id)`）。

## 明确不做

- Stripe Customer Portal
- 取消时自动退款或自动清零次数
- Dashboard 退款的自动同步撤销次数（仅本系统退款按钮可选 revoke）
