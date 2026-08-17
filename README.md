---

# Bebcare AI Studio

全自动社媒内容生成与发布系统，面向 Bebcare 婴儿产品品牌。系统根据产品资产与可配置的提示词维度，自动生成英文社媒文案与产品图，经去重与人工审核后，通过 Buffer 发布到 Instagram、Facebook、TikTok 等多平台。

> 根目录部署到 Hugging Face Space 时，本文件顶部 YAML（`sdk: docker`）供 Space 识别。**业务开发请改** `backend/` **与** `frontend/`，再同步部署副本。

## 核心特性

- **产品资产管理**：产品 CRUD、参考图（产品图 / 场景图）上传与 CDN 持久化
- **多维提示词引擎**：场景、光线、构图、风格等维度可配置；支持产品类型兼容策略与平台语气
- **文案 + 出图流水线**：DeepSeek（百炼兼容）生成英文文案与中文图像 Prompt；豆包等 Provider 出图
- **图文去重**：pHash（图像）+ MinHash（文案）；可选 CLIP 向量相似度（默认关闭）
- **双模式发布**：`auto` 直发 Buffer；`manual` 生成草稿供人工挑选后再发
- **Cron 调度**：APScheduler 定时任务，全局并发控制，适配 HF Space 资源
- **多平台触达**：Buffer GraphQL，覆盖 Instagram、Facebook、TikTok、X、LinkedIn 等
- **管理后台**：React 管理台（资产 / 维度 / 任务 / 待发 / 预览 / 日历 / Provider / 用户）
- **可部署副本**：`hf-space/`、`space4/` 由脚本从 `backend/` 同步，CI 漂移门禁



## 技术栈


| 组件          | 技术                                        |
| ----------- | ----------------------------------------- |
| 后端框架        | Python 3.10+，FastAPI，Uvicorn              |
| ORM / 迁移    | SQLAlchemy 2，Alembic                      |
| 数据库         | 本地 SQLite；生产 Supabase PostgreSQL          |
| 调度          | APScheduler（时区 Asia/Shanghai）             |
| 向量 / 元数据    | ChromaDB；（可选）CLIP / Torch                 |
| 去重          | imagehash（pHash）、datasketch（MinHash）      |
| 认证          | JWT（HS256），密码哈希                           |
| 文案 / Prompt | DeepSeek Chat Completions（百炼 OpenAI 兼容）   |
| 图像生成        | 豆包等可插拔 Image Provider                     |
| 发布          | Buffer GraphQL API                        |
| 图床          | GitHub Repository → CDN URL               |
| 前端          | React 19，Vite 6，TypeScript，Tailwind CSS 3 |
| 部署          | HF Space（Docker）、Vercel、魔搭创空间             |




## 主要流程

1. **配置资产**：录入产品与参考图，绑定提示词维度
2. **配置任务**：设置 Cron、目标品类/产品、平台、出图/文案数量、`auto` / `manual` 模式
3. **调度触发**：APScheduler 按 Cron 执行（同任务不重叠，全局信号量限并发）
4. **组装 Prompt**：PromptEngine 按平台风格、叙事视角、写作风格与维度拼装
5. **生成内容**：DeepSeek 产出英文文案 + 中文图像提示词 → 图像 Provider 出图
6. **去重过滤**：pHash / MinHash（可选 CLIP）剔除近似重复
7. **落盘 CDN**：生成图上传 GitHub 图床，得到持久 URL
8. **发布分支**：
  - `auto` → Buffer 直发目标平台
  - `manual` → 写入 `ManualTaskDraft`，运营在待发页挑选后发布或丢弃

也可在管理台 `/preview` 手动试生成，或通过 `/v1/generate` API 触发。

## 安装与配置



### 1. 后端

```bash
cd backend
cp .env.example .env          # 填写密钥；本地可省略 DATABASE_URL（默认 SQLite）
pip install -r requirements.txt
uvicorn bebcare.main:app --host 0.0.0.0 --port 8080 --reload
```

- 探活：`GET http://localhost:8080/health`
- OpenAPI：`http://localhost:8080/docs`

可选 CLIP（图文向量去重）：

```bash
pip install -r requirements-clip.txt
# .env 中 ENABLE_CLIP=true，并准备 Long-CLIP 权重
```



### 2. 前端

```bash
cd frontend
npm ci
npm run dev                   # http://localhost:5174，/v1 代理到 :8080
```

本地一般**无需**配置 `VITE_`*。生产（Vercel）配置 `HF_SPACE_HOST`，**不要**把 `http://*.hf.space` 打进前端包（会 Mixed Content）。

### 3. 配置环境变量

复制 `backend/.env.example` 为 `.env`，关键项示例：

```env
# 环境：development | production
APP_ENV=development

# 数据库（本地可省略，默认 SQLite；生产必须 Postgres）
# DATABASE_URL=postgresql://postgres.[ref]:[password]@...:5432/postgres?sslmode=require
AUTO_MIGRATE=true

# 调度与连接池（HF Space 建议保守）
SCHEDULER_MAX_WORKERS=2
SCHEDULER_MAX_INSTANCES=1
MAX_CONCURRENT_JOBS=1
DB_POOL_SIZE=8
ENABLE_CLIP=false

# DeepSeek / 百炼（填 OpenAI 兼容 base 即可，代码会补全 /chat/completions）
DEEPSEEK_API_KEY=your_bailian_api_key
DEEPSEEK_API_URL=https://.../compatible-mode/v1
DEEPSEEK_MODEL=deepseek-v4-pro

# 可选：视觉写 Prompt（多模态模型）
# VISION_API_KEY=
# VISION_API_URL=
VISION_MODEL=qwen3.5-omni-plus-2026-03-15

# 豆包图像
DOUBAO_API_KEY=your_doubao_api_key
DOUBAO_API_URL=https://ark.cn-beijing.volces.com/api/v3/images/generations
DOUBAO_MODEL_ID=ep-xxxxxxxx

# Buffer / GitHub 图床
BUFFER_API_TOKEN=your_buffer_api_token
GITHUB_TOKEN=your_github_token
GITHUB_USERNAME=your_github_username
GITHUB_REPO=your_github_repo
GITHUB_BRANCH=main

# 安全（JWT + Provider Key 加密）
SECRET_KEY=your_secret_key_here_must_be_32_characters_long_minimum
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@bebcare.com
ADMIN_PASSWORD=change-me-on-first-boot

# 应用
APP_HOST=0.0.0.0
APP_PORT=8080
LOG_LEVEL=INFO
ALLOWED_ORIGINS=http://localhost:5174,http://127.0.0.1:5174
```

生产务必设置：`APP_ENV=production`、`DATABASE_URL`（Supabase）、`ALLOWED_ORIGINS`（前端域名白名单，禁止 `*`）、以及全部密钥类变量。

### 4. 数据库迁移

迁移文件：`backend/migrations/versions/`（本地 SQLite 与生产 Postgres 共用）。当前 head：`016_dimension_scope_unique`。

**本地开发**（在 `backend/` 目录）：

```bash
cd backend
pip install -r requirements.txt

# 默认 AUTO_MIGRATE=true：重启 uvicorn 即自动升级
uvicorn bebcare.main:app --host 0.0.0.0 --port 8080 --reload

# 或先手动升级再启动
python -m alembic upgrade head
python -m alembic current   # 应含 (head) 或 016_dimension_scope_unique
```

**生产（HF Space + Supabase）**：

1. `python scripts/sync_deploy_copies.py` 后部署新镜像
2. Space Secrets：`APP_ENV=production`、`DATABASE_URL`（Session `5432` + `sslmode=require`）
3. `AUTO_MIGRATE=true`（单实例推荐）→ 重启 Space；或 `AUTO_MIGRATE=false` 时在发布前执行：

```bash
cd backend
export DATABASE_URL="postgresql://..."   # 勿提交到 Git
export APP_ENV=production
python -m alembic upgrade head
```

大版本迁移前请备份 Supabase。Bebcare 生产可选 `SEED_BABY_DIMENSIONS=true`。详见 `[backend/README.md](backend/README.md)` 与 `[项目说明.md](项目说明.md)` §8.2。

**维护者** — 改完 models 后：

```bash
cd backend
python -m alembic revision --autogenerate -m "describe change"
python -m alembic upgrade head
python ../scripts/sync_deploy_copies.py
```

已有本地 SQLite（以前靠 `create_all`）首次切换可：`python scripts/stamp_existing_db.py`（通常启动已自动处理）。



## 使用方式



### 1. 本地联调

1. 启动后端（`:8080`）与前端（`:5174`）
2. 使用 `ADMIN_*` 账号登录管理台
3. 在 **资产** 录入产品与参考图
4. 在 **维度** 配置提示词维度并绑定产品类型
5. 在 **预览** 试生成文案/图片，或在 **任务** 配置 Cron
6. **人工模式**：到 **待发** 挑选图文并发布；**自动模式**：任务执行后直发 Buffer



### 2. API 概览

前缀 `/v1`。完整契约以 `/docs` 为准。


| 路由组                  | 能力                             |
| -------------------- | ------------------------------ |
| `/auth`              | 登录、刷新 Token、当前用户、用户 CRUD       |
| `/products`          | 产品与分类、参考图上传/列表/删除              |
| `/tasks`             | 定时任务 CRUD、草稿、CDN 重传、发布/丢弃、执行记录 |
| `/generate`          | 综合生成、仅文案、仅出图、异步状态轮询            |
| `/publish`           | 发起发布、查询发布状态                    |
| `/prompt-dimensions` | 维度类型/CRUD、兼容策略、产品维度绑定          |
| `/image-providers`   | Provider CRUD、模型列表、连通性测试       |


探活（无需登录）：`GET /`、`GET /health`。

### 3. 同步部署副本

业务改动只改 `backend/`，再同步：

```bash
python scripts/sync_deploy_copies.py          # 同步到 hf-space/、space4/
python scripts/sync_deploy_copies.py --check  # 检查漂移（CI 门禁）
```



## 生产部署



### 推荐拓扑


| 组件  | 建议                                                  |
| --- | --------------------------------------------------- |
| 后端  | Hugging Face Space（Docker，端口 7860）                  |
| 前端  | Vercel（`/v1` 由 Edge Function 代理到 Space）             |
| 数据库 | Supabase Postgres，`APP_ENV=production`              |
| 密钥  | Space Settings → Secrets（见 `hf-space/.env.example`） |




### Hugging Face Space

HF **只认仓库根目录**的 `Dockerfile` 与带 `sdk: docker` 的 `README.md`，不会读取 `hf-space/Dockerfile`。

推荐：将本单体仓库推到 Space；根目录 `Dockerfile` 从 `hf-space/` 复制应用代码。

本地验证部署包：

```bash
cd hf-space
docker build -t bebcare-api .
docker run --rm -p 7860:7860 --env-file .env bebcare-api
curl http://127.0.0.1:7860/health
```

详情见 `hf-space/README.md`。魔搭创空间见 `space4/README.md`。

### 前端（Vercel）

- 环境变量：`HF_SPACE_HOST`（hostname，不要带 `https://`）
- 勿设置会打进包的 `VITE_BACKEND_URL=http://...`
- 后端 `ALLOWED_ORIGINS` 须包含前端域名



### CI（GitHub Actions）

`.github/workflows/ci.yml`：

- 后端 `pytest`
- 前端 `npm run build`
- `sync_deploy_copies.py --check`



## 项目结构

```
Bebcare_Buffer2.0/
├── backend/                      # 开发主源码
│   ├── bebcare/
│   │   ├── api/                  # 路由（auth / products / tasks / generate …）
│   │   ├── config/               # pydantic-settings 配置
│   │   ├── db/                   # 数据库会话
│   │   ├── models/ schemas/      # ORM 与 Pydantic
│   │   ├── services/             # 业务服务
│   │   ├── generator/            # 文案 / 出图流水线
│   │   ├── prompt_builder/       # Prompt 引擎与平台风格
│   │   ├── dedup/                # pHash / MinHash / CLIP
│   │   ├── publisher/            # Buffer 发布客户端
│   │   ├── scheduler/            # APScheduler 定时任务
│   │   ├── knowledge_base/       # Chroma / Embedding
│   │   ├── providers/            # 图像 Provider 适配
│   │   ├── utils/ tasks/
│   │   └── main.py
│   ├── migrations/               # Alembic
│   ├── tests/                    # pytest（api / unit）
│   ├── scripts/                  # stamp 等工具
│   ├── .env.example
│   └── requirements*.txt
├── frontend/                     # 管理后台
│   ├── src/
│   │   ├── api/                  # Axios 客户端
│   │   ├── pages/                # 登录 / 资产 / 维度 / 任务 …
│   │   ├── components/
│   │   └── lib/
│   ├── api/                      # Vercel /v1 代理
│   └── vercel.json
├── hf-space/                     # HF Space 部署副本
├── space4/                       # 魔搭创空间部署副本
├── scripts/
│   └── sync_deploy_copies.py     # 同步 / --check
├── docs/                         # 可选文档副本
├── 项目书.md                     # 建设目标、里程碑、风险
├── 项目说明.md                   # 交付说明与日常使用
└── README.md
```



## 内容生成与去重策略

- **Prompt 引擎**：平台语气（IG / TikTok / FB 等）、叙事视角、写作风格、硬性负向提示（水印、文字、商标变形等）
- **文案模型**：DeepSeek Chat Completions；`DEEPSEEK_API_URL` 支持百炼兼容 base 自动补全路径
- **图像 Prompt**：可面向婴儿产品商业摄影；可选多模态「视觉写 Prompt」
- **去重**：
  - **pHash**：汉明距离阈值，防近似重复图
  - **MinHash / LSH**：文案近重复
  - **CLIP（可选）**：`ENABLE_CLIP=true` 时启用图向量相似度
- **调度**：`max_instances` + `coalesce`；`MAX_CONCURRENT_JOBS` 全局信号量；HF 建议并发为 1



## 配置参数表


| 参数名                       | 说明                            | 典型值               |
| ------------------------- | ----------------------------- | ----------------- |
| `APP_ENV`                 | 运行环境；production 禁止 SQLite     | `development`     |
| `DATABASE_URL`            | 数据库连接；本地可省略                   | （SQLite 默认）       |
| `AUTO_MIGRATE`            | 启动时 alembic upgrade           | `true`            |
| `SEED_BABY_DIMENSIONS`    | 启动时追加 baby_family 视觉预设   | `false`（Bebcare 生产可 `true`） |
| `MAX_CONCURRENT_JOBS`     | 全局调度并发                        | `1`               |
| `SCHEDULER_MAX_WORKERS`   | 调度线程池                         | `2`               |
| `SCHEDULER_MAX_INSTANCES` | 单任务最大重叠实例                     | `1`               |
| `DB_POOL_SIZE`            | SQLAlchemy 池大小（Supabase 宜小）   | `3`～`8`           |
| `ENABLE_CLIP`             | 是否启用 CLIP 去重                  | `false`           |
| `DEEPSEEK_API_KEY`        | 文案 / Prompt API Key           | （必填）              |
| `DEEPSEEK_API_URL`        | OpenAI 兼容 base URL            | （必填）              |
| `DEEPSEEK_MODEL`          | 文案模型名                         | `deepseek-v4-pro` |
| `VISION_MODEL`            | 可选多模态写 Prompt 模型              | 见 `.env.example`  |
| `DOUBAO_API_KEY`          | 默认图像 Provider Key             | （必填）              |
| `BUFFER_API_TOKEN`        | Buffer GraphQL Token          | （必填）              |
| `GITHUB_*`                | 图床仓库凭证                        | （必填）              |
| `SECRET_KEY`              | JWT + Provider Key 加密（≥32 字符） | （必填）              |
| `ADMIN_PASSWORD`          | 首次初始化管理员密码                    | （必填）              |
| `ALLOWED_ORIGINS`         | CORS 白名单（逗号分隔，禁止 `*`）         | 本地含 `:5174`       |
| `LOG_LEVEL`               | 日志级别                          | `INFO`            |
| `APP_PORT`                | 本地监听端口（HF 镜像内为 7860）          | `8080`            |




## 前端页面


| 路由              | 模块               |
| --------------- | ---------------- |
| `/login`        | JWT 登录           |
| `/assets`       | 产品与参考图           |
| `/dimensions`   | 提示词维度            |
| `/tasks`        | 定时任务配置           |
| `/pending`      | 待发审核（人工草稿）       |
| `/preview`      | 内容试生成            |
| `/calendar`     | 发布日历             |
| `/image-models` | 图像 Provider（管理员） |
| `/users`        | 用户管理（管理员）        |




## 测试覆盖

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

覆盖 auth / generate 契约与少量单元测试。前端：

```bash
cd frontend
npm ci
npm run build    # 含 TypeScript 检查
npm run lint
```



## 注意事项

1. **开发只改** `backend/`，部署前执行同步脚本；CI 对 `hf-space/`、`space4/` 做漂移检查
2. 生产 **禁止 SQLite**；未配置 Postgres 时 `APP_ENV=production` 会启动失败
3. HF Space 资源有限：`MAX_CONCURRENT_JOBS=1`，错开 Cron，避免多任务同一分钟触发
4. Supabase 免费连接数有限，勿盲目加大 `DB_POOL_SIZE`
5. `SECRET_KEY` 同时用于 JWT 与 Provider API Key 加密，生产只放 Secrets，不入库
6. `ALLOWED_ORIGINS` 必须为显式白名单；禁止 `*` 与 credentials 组合
7. 首次启动用 `ADMIN_PASSWORD` 初始化管理员；勿在日志依赖明文密码
8. `DEEPSEEK_API_URL` 填到 `…/compatible-mode/v1` 即可，勿手写重复的 `/chat/completions`
9. 开启 CLIP 需额外依赖与权重，默认关闭以降低 Space 成本
10. GitHub 图床仓库可见性与内容合规需自行管控；婴儿产品广告注意平台审核与人工模式
11. 第三方 API（DeepSeek / 豆包 / Buffer）存在限流与变更风险，失败执行可在任务执行记录中排查
12. 规划与里程碑见 `项目书.md`；上手与运维见 `项目说明.md`；分目录说明见 `backend/README.md`、`frontend/README.md`、`hf-space/README.md`



## License

内部项目；对外许可以仓库所有者声明为准。