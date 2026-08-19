# Bebcare AI Studio — 后端

开发主源码目录。业务改动请在此进行，再通过 `scripts/sync_deploy_copies.py` 同步到 `hf-space/`、`space4/`。

## 本地启动

```bash
cd backend
cp .env.example .env    # 按需填写密钥；本地可省略 DATABASE_URL（默认 SQLite）
pip install -r requirements.txt
uvicorn bebcare.main:app --host 0.0.0.0 --port 8888 --reload
```

| 入口 | 地址 |
|------|------|
| 健康检查 | `GET /health` |
| OpenAPI | `/docs`、`/redoc` |
| 业务 API | `/v1/*` |

生产 / HF Space 默认端口为 **7860**；本地与前端 Vite 代理约定为 **8888**。

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
| `ALLOWED_ORIGINS` | `http://localhost:5174,...` | 前端域名白名单（禁止 `*`） |

必填密钥类：`DEEPSEEK_*`、`DOUBAO_*`、`BUFFER_*`、`GITHUB_*`、`SECRET_KEY`、`ADMIN_PASSWORD`。

`DEEPSEEK_API_URL` 可填百炼 OpenAI 兼容 base（如 `…/compatible-mode/v1`），代码会自动补全 `/chat/completions`；模型默认 `deepseek-v4-pro`（可用 `DEEPSEEK_MODEL` 覆盖）。

生产环境若仍使用 SQLite，启动会直接报错。

## 数据库迁移（Alembic）

迁移脚本目录：`migrations/versions/`（本地 SQLite 与生产 Supabase Postgres **共用同一套**）。

当前 head revision：`016_dimension_scope_unique`（链：`013_brands` 品牌表 → `014` 产品品牌语音开关 → `015` 品牌 Logo → `016` 视觉风格作用域唯一约束）。

所有 Alembic 命令均在 **`backend/` 目录**下执行。Windows / 未装全局 CLI 时，请用 `python -m alembic` 代替 `alembic`。

### 拉取代码后：本地开发

1. 安装/更新依赖：`pip install -r requirements.txt`
2. 确认 `.env` 存在（`cp .env.example .env`）；本地可省略 `DATABASE_URL`（默认 `bebcare.db`）
3. **升级 schema（二选一）**

**方式 A — 推荐（默认）**  
保持 `AUTO_MIGRATE=true`，重启后端即可自动 `upgrade head`：

```bash
cd backend
uvicorn bebcare.main:app --host 0.0.0.0 --port 8888 --reload
```

**方式 B — 先手动迁移再启动**（适合排查迁移错误）：

```bash
cd backend
python -m alembic upgrade head
uvicorn bebcare.main:app --host 0.0.0.0 --port 8888 --reload
```

4. **验证是否已到 head**：

```bash
cd backend
python -m alembic current
# 期望输出含 016_dimension_scope_unique 或 (head)
```

启动日志中应出现 `Running database migrations` 或 `Database ready`。

**本地说明**

| 场景 | 行为 |
|------|------|
| 全新 SQLite | 迁移建表；首次启动种子管理员与 Generic / Bebcare 品牌 |
| 旧库无 `alembic_version` 表 | 启动时自动 `stamp head` 并补缺失表 |
| 仅通用视觉预设 | 默认行为，无需操作 |
| 需要母婴视觉预设 | `.env` 设 `SEED_BABY_DIMENSIONS=true` 后重启 |

**迁移 016 注意**：会删除 `prompt_dimensions` 中 `(product_type, dimension_type, item_id)` 重复行（每组只保留最小 `dimension_id`）。本地若有自定义重复 ID，升级前请备份 `bebcare.db`。

### 生产部署（HF Space + Supabase）

1. 合并/拉取含新迁移的代码后，同步部署副本：`python scripts/sync_deploy_copies.py`
2. 在 HF Space **Secrets** 中确认：
   - `APP_ENV=production`
   - `DATABASE_URL` = Supabase Session 连接串（端口 `5432`，`sslmode=require`）
   - `AUTO_MIGRATE=true`（单实例 Space，**推荐**）
   - Bebcare 生产需要母婴预设时：`SEED_BABY_DIMENSIONS=true`
3. **升级 schema（二选一）**

**方式 A — 单实例自动（推荐）**  
`AUTO_MIGRATE=true` 时，部署新镜像后 **重启 / Factory reboot Space**。查看 Logs，应出现 `Running database migrations` 与 `Database ready`。

**方式 B — 手动迁移（多实例、或 `AUTO_MIGRATE=false`）**  
在能访问生产库的环境执行（**勿将 `DATABASE_URL` 提交到 Git**）：

```bash
cd backend
# bash:
export DATABASE_URL="postgresql://postgres.[ref]:[password]@....supabase.com:5432/postgres?sslmode=require"
export APP_ENV=production
python -m alembic upgrade head
python -m alembic current
```

```powershell
# PowerShell:
cd backend
$env:DATABASE_URL = "postgresql://..."
$env:APP_ENV = "production"
python -m alembic upgrade head
python -m alembic current
```

确认 `(head)` 后再发布或重启应用。若 `AUTO_MIGRATE=false`，应用启动**不会**自动迁移，必须由流水线或运维先执行上述命令。

**生产注意**

- 大版本迁移（尤其 `013_brands`、`016_dimension_scope_unique`）前，请在 Supabase Dashboard 做数据库备份
- `APP_ENV=production` 时禁止使用 SQLite
- `hf-space/migrations/` 须与 `backend/migrations/` 一致；CI 会跑 `sync_deploy_copies.py --check`

### 维护者：新增迁移

```bash
cd backend
python -m alembic revision --autogenerate -m "describe change"
python -m alembic upgrade head
python ../scripts/sync_deploy_copies.py
```

已有本地 SQLite（以前靠 `create_all`）首次切换时，启动会自动 `stamp`；也可手动：

```bash
python scripts/stamp_existing_db.py
```

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
