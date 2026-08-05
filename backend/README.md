# Bebcare AI Studio — 后端

开发主源码目录。业务改动请在此进行，再通过 `scripts/sync_deploy_copies.py` 同步到 `hf-space/`、`space4/`。

## 本地启动

```bash
cd backend
cp .env.example .env    # 按需填写密钥；本地可省略 DATABASE_URL（默认 SQLite）
pip install -r requirements.txt
uvicorn bebcare.main:app --host 0.0.0.0 --port 8080 --reload
```

| 入口 | 地址 |
|------|------|
| 健康检查 | `GET /health` |
| OpenAPI | `/docs`、`/redoc` |
| 业务 API | `/v1/*` |

生产 / HF Space 默认端口为 **7860**；本地与前端 Vite 代理约定为 **8080**。

## 环境变量

完整模板见 `.env.example`。要点：

| 变量 | 本地 | 生产（Supabase） |
|------|------|------------------|
| `APP_ENV` | `development` | `production` |
| `DATABASE_URL` | 可省略（SQLite `bebcare.db`） | Postgres Session `5432` + `sslmode=require` |
| `AUTO_MIGRATE` | `true` | 单实例可 `true`；多实例建议 `false`，由 CI 跑迁移 |
| `MAX_CONCURRENT_JOBS` | `1`～`2` | HF Space 建议 `1`；错开 cron |
| `SCHEDULER_MAX_WORKERS` | `2` | 线程池大小 |
| `DB_POOL_SIZE` | 按需 | 免费连接有限，建议 `3` 左右 |
| `ENABLE_CLIP` | `false` | 开启需 `requirements-clip.txt` + Long-CLIP |
| `ALLOWED_ORIGINS` | `http://localhost:5173,...` | 前端域名白名单（禁止 `*`） |

必填密钥类：`DEEPSEEK_*`、`DOUBAO_*`、`BUFFER_*`、`GITHUB_*`、`SECRET_KEY`、`ADMIN_PASSWORD`。

`DEEPSEEK_API_URL` 可填百炼 OpenAI 兼容 base（如 `…/compatible-mode/v1`），代码会自动补全 `/chat/completions`；模型默认 `deepseek-v4-pro`（可用 `DEEPSEEK_MODEL` 覆盖）。

生产环境若仍使用 SQLite，启动会直接报错。

## 数据库迁移（Alembic）

本地与生产共用 `migrations/versions/`。

```bash
pip install -r requirements.txt

# 手动升级到最新（可选；默认 AUTO_MIGRATE=true 启动时执行）
alembic upgrade head

# 改完 models 后新建迁移
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

已有本地 SQLite（以前靠 `create_all`）首次切换时，启动会自动 `stamp`；也可手动：

```bash
python scripts/stamp_existing_db.py
```

上线到 Supabase：写入生产 `DATABASE_URL` → `APP_ENV=production` → 部署前或启动时执行 `alembic upgrade head`。

## API 概览

前缀 `/v1`。完整契约以 `/docs` 为准。

| 路由组 | 能力 |
|--------|------|
| `/auth` | 登录、刷新 Token、当前用户、用户 CRUD |
| `/products` | 产品与分类、参考图上传/列表/删除 |
| `/tasks` | 定时任务 CRUD、草稿、CDN 重传、发布/丢弃、执行记录 |
| `/generate` | 综合生成、仅文案、仅出图、异步状态轮询 |
| `/publish` | 发起发布、查询发布状态 |
| `/prompt-dimensions` | 维度类型/CRUD、兼容策略、产品维度绑定 |
| `/image-providers` | Provider CRUD、模型列表、连通性测试 |

## 测试

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

覆盖 auth / generate 契约与少量单元测试。CI 见仓库根目录 `.github/workflows/ci.yml`。

## 技术栈

FastAPI · Uvicorn · SQLAlchemy 2 + Alembic · PostgreSQL（生产）/ SQLite（本地）· ChromaDB · APScheduler ·（可选）PyTorch / Transformers
