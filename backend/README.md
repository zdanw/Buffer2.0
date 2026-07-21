---
title: Bebcare AI Studio API
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
---

# Bebcare AI Studio API

全自动社媒内容生成与发布系统后端服务

## 启动方式

```bash
uvicorn app:app --host 0.0.0.0 --port 7860
```

## 环境变量

完整模板见 `.env.example`。要点：

| 变量 | 本地 | 生产（Supabase） |
|------|------|------------------|
| `APP_ENV` | `development` | `production` |
| `DATABASE_URL` | 可省略（默认 SQLite `bebcare.db`） | Supabase `postgresql://...`（Session 5432 + `sslmode=require`） |
| `AUTO_MIGRATE` | `true` | 单实例可 `true`；多实例建议 `false` 并由 CI 跑迁移 |
| `MAX_CONCURRENT_JOBS` | `1`～`2` | HF Space 建议 `1`；错开 cron，勿多任务同一分钟触发 |
| `SCHEDULER_MAX_WORKERS` | `2` | 线程池大小 |
| `DB_POOL_SIZE` | `3` | Supabase 免费连接有限，勿盲目加大 |
| `ENABLE_CLIP` | `false` | 图文向量/匹配；开启需 `requirements-clip.txt` + Long-CLIP |

生产环境若仍使用 SQLite，启动会直接报错。

## 数据库迁移（Alembic）

本地与生产共用同一套 migration（`migrations/versions/`）。

```bash
# 安装依赖后，在 backend 目录
pip install -r requirements.txt

# 手动升级到最新（可选；默认启动时 AUTO_MIGRATE=true 会自动执行）
alembic upgrade head

# 新建迁移（改完 models 后）
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

已有本地 SQLite（以前靠 `create_all`）首次切换时，启动会自动 `stamp`；也可手动：

```bash
python scripts/stamp_existing_db.py
```

上线到 Supabase：在控制台拿到 Session 连接串 → 写入生产 `DATABASE_URL` → `APP_ENV=production` → 部署前/启动时执行 `alembic upgrade head`。

## API 接口

前缀为 `/v1`：

- `POST /v1/auth/login/` - 用户登录
- `GET /v1/auth/me` - 获取当前用户信息
- `GET /v1/auth/users` - 获取用户列表
- `POST /v1/auth/users` - 创建用户
- `PUT /v1/auth/users/{user_id}` - 更新用户
- `DELETE /v1/auth/users/{user_id}` - 删除用户

## 技术栈

- FastAPI 0.110.0
- Uvicorn
- SQLAlchemy 2.0 + Alembic
- PostgreSQL（生产 / Supabase）或 SQLite（本地）
- ChromaDB
- PyTorch
- Transformers