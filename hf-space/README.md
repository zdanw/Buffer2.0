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

本目录为可独立推送到 HF Space 的自包含副本，与仓库内 `backend/` 源码对应。**开发请改 `backend/`**，再执行：

```bash
python scripts/sync_deploy_copies.py
```

## 部署到 Hugging Face Space

**重要：** HF 只认仓库**根目录**的 `Dockerfile` 与带 `sdk: docker` 的 `README.md`，**不会**读取本目录下的 `Dockerfile`。

### 方式 A：推送整个单体仓库（推荐）

将本 Git 仓库推到 Space 远程。根目录已有：

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
| `DB_POOL_SIZE` | `16`（对比模式并行轮询；Supabase 仍须留余量） |
| `DB_MAX_OVERFLOW` | `16` |
| `ENABLE_CLIP` | `false`（开启需额外依赖与 Long-CLIP） |
| `LOG_LEVEL` | `INFO` |
| `ALLOWED_ORIGINS` | 前端域名白名单（逗号分隔，禁止 `*`） |

必填密钥：`DEEPSEEK_API_KEY`、`DOUBAO_API_KEY`、`BUFFER_API_TOKEN`、`GITHUB_*`、`SECRET_KEY`、`ADMIN_PASSWORD`。

生产禁止使用 SQLite；未配置 Postgres 时启动会失败。

## 数据库迁移（部署必读）

`hf-space/migrations/` 与 `backend/migrations/` 同步；当前 head：`016_dimension_scope_unique`。

### 单实例 Space（推荐）

1. 推送含新迁移的代码并重建 Space
2. Secrets 保持 `AUTO_MIGRATE=true`
3. **重启 Space** — 启动日志应出现 `Running database migrations` → `Database ready`

### 手动迁移（`AUTO_MIGRATE=false` 或先迁后发）

在能访问生产 `DATABASE_URL` 的环境执行（仓库根目录或 `hf-space/` 副本内路径等价）：

```bash
cd hf-space   # 或本地 backend/，迁移文件相同
export DATABASE_URL="postgresql://postgres.[ref]:[password]@....supabase.com:5432/postgres?sslmode=require"
export APP_ENV=production
python -m alembic upgrade head
python -m alembic current
```

PowerShell：`$env:DATABASE_URL = "..."`；`$env:APP_ENV = "production"`。

确认 `(head)` 后再滚动发布。若应用侧 `AUTO_MIGRATE=false`，**不会**在启动时补跑迁移。

### 生产注意

| 项 | 说明 |
|----|------|
| 备份 | 升级 `013_brands` / `016_dimension_scope_unique` 前在 Supabase 做快照 |
| Bebcare 预设 | `SEED_BABY_DIMENSIONS=true` 启动时追加 `baby_family` 视觉风格 |
| 漂移检查 | 发布前跑 `python scripts/sync_deploy_copies.py --check` |

更完整的本地与生产步骤见仓库根目录 `[backend/README.md](../backend/README.md)`、`[项目说明.md](../项目说明.md)` §8.2。

## API

前缀 `/v1`。探活：`GET /`、`GET /health`。完整契约见运行中的 `/docs`。

## 技术栈

FastAPI · Uvicorn · SQLAlchemy 2 + Alembic · PostgreSQL / SQLite · ChromaDB · APScheduler
