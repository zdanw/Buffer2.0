---
title: Bebcare AI Studio API
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
---

# Bebcare AI Studio API

全自动社媒内容生成与发布系统后端（Hugging Face Space 部署包）。

本目录为可独立推送到 HF Space 的自包含副本，与仓库内 `backend/` 源码对应。

## 部署到 Hugging Face Space

**重要：** HF 只认仓库**根目录**的 `Dockerfile` 与带 `sdk: docker` 的 `README.md`，**不会**读取子目录 `hf-space/Dockerfile`。

推荐两种方式（二选一）：

### 方式 A：推送整个单体仓库（当前推荐）

把本 Git 仓库推到 Space 远程。根目录已有：

- `README.md`（`sdk: docker` + `app_port: 7860`，**不要**写 `app_file`）
- `Dockerfile`（从 `hf-space/` 复制应用代码）
- `app.py`（兼容入口）

Space 创建时 SDK 选 **Docker**；若曾建成 Gradio，改根目录 README 的 YAML 为 `sdk: docker` 后 Factory reboot。

### 方式 B：仅推送本目录内容

把 `hf-space/` **内的文件**（不是 `hf-space` 文件夹本身）放到 Space 仓库根目录，使 `Dockerfile`、`README.md`、`bebcare/` 位于根路径。

本地验证（方式 B）：

```bash
cd hf-space
docker build -t bebcare-api .
docker run --rm -p 7860:7860 --env-file .env bebcare-api
```

Secrets / Variables 配置环境变量后等待构建；探活：`GET /health`。
## 环境变量

完整模板见 `.env.example`。HF Space 生产建议：

| 变量 | 建议值 |
|------|--------|
| `APP_ENV` | `production` |
| `DATABASE_URL` | Supabase `postgresql://...`（Session 5432 + `sslmode=require`） |
| `AUTO_MIGRATE` | `true`（单实例）；多实例用 CI 跑迁移 |
| `MAX_CONCURRENT_JOBS` | `1` |
| `SCHEDULER_MAX_WORKERS` | `2` |
| `DB_POOL_SIZE` | `3` |
| `ENABLE_CLIP` | `false`（开启需额外依赖与 Long-CLIP） |
| `LOG_LEVEL` | `INFO`（`DEBUG`/`WARNING`/`ERROR`；日志在 Space → Logs） |
| `ALLOWED_ORIGINS` | 前端域名白名单（逗号分隔，禁止 `*`） |

必填密钥类：`DEEPSEEK_API_KEY`、`DOUBAO_API_KEY`、`BUFFER_API_TOKEN`、`GITHUB_*`、`SECRET_KEY`、`ADMIN_PASSWORD`。

生产环境禁止使用 SQLite；未配置 Postgres 时启动会失败。

## API

前缀 `/v1`。根路径 `/` 与 `/health` 可用于探活。

## 技术栈

FastAPI · Uvicorn · SQLAlchemy 2 + Alembic · PostgreSQL / SQLite · ChromaDB · APScheduler
