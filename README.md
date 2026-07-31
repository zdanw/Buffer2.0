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

业务代码副本在 `hf-space/`（及魔搭 `space4/`）；**开发请改 `backend/`**，再同步后部署：

```bash
python scripts/sync_deploy_copies.py          # 同步
python scripts/sync_deploy_copies.py --check  # 检查是否漂移
```

`DEEPSEEK_API_URL` 可填百炼云 OpenAI 兼容 base（如 `…/compatible-mode/v1`），代码会自动补全 `/chat/completions`；模型默认 `deepseek-v4-pro`（可用 `DEEPSEEK_MODEL` 覆盖）。

CI（`.github/workflows/ci.yml`）会跑后端 `pytest`、前端 build，以及 `--check` 漂移门禁。
