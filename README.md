---
title: Bebcare AI Studio API
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
---

# Bebcare AI Studio API

全自动社媒内容生成与发布系统后端。

本仓库以 **Docker SDK** 部署到 Hugging Face Space。入口为根目录 `Dockerfile`（构建上下文来自 `hf-space/`）。

## 健康检查

- `GET /` — 欢迎信息
- `GET /health` — `{"status":"healthy"}`

## 环境变量

在 Space **Settings → Secrets** 中配置，模板见 `hf-space/.env.example`。

生产务必设置：

- `APP_ENV=production`
- `DATABASE_URL`（Supabase Postgres，勿用 SQLite）
- API / 认证相关密钥（`DEEPSEEK_*`、`DOUBAO_*`、`BUFFER_*`、`GITHUB_*`、`SECRET_KEY`、`ADMIN_PASSWORD`）
- `ALLOWED_ORIGINS`（前端域名白名单）

## 说明

业务代码副本在 `hf-space/`；开发请改 `backend/`，再同步到 `hf-space/` 后重新部署。
