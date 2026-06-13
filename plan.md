基于您的反馈，我对整个项目计划书进行了结构性优化。除了修正接口设计外，还强化了异步处理、安全机制与可观测性，使其更贴近企业级生产标准。以下为全新版本。

---

# Bebcare 全自动社媒内容生成与发布系统 实施计划书 V2.0

**项目代号**：Bebcare AI Studio  
**版本**：V2.0  
**日期**：2026-06-11  

---

## 目录
1. 项目概述与目标
2. 系统总体架构
3. 技术选型与版本
4. 核心模块详细设计
5. RESTful API 接口规范
6. 提示词构建与内容生成引擎
7. 向量知识库设计
8. 自动化调度与发布流程
9. 去重与质量保证
10. 部署与运维方案
11. 测试策略
12. 安全与合规
13. 风险与应对
14. 项目排期与资源

---

## 1. 项目概述与目标
### 1.1 背景
Bebcare 母婴硬件品牌需在 TikTok、Instagram、Facebook 持续产出高质量视觉图文。当前人工创作效率低、风格波动大。急需一套基于 AI 的端到端自动化内容工厂，实现从知识库提取、智能创作、去重校验到多平台发布的闭环。

### 1.2 目标
- 建立多模态向量知识库，存储产品图像、文案与元数据。
- 构建动态提示词系统，驱动 DeepSeek 文案生成与 Doubao-Seedream-4.5 图像生成。
- 实现三层去重保障内容原创性。
- 集成 GitHub+jsDelivr 图床与 Buffer 社交分发。
- 提供用户可配置的全自动定时任务，零人工干预。

---

## 2. 系统总体架构
```
┌──────────────────────────────────────────────────┐
│                 前端 (React/Vue)                  │
│       任务配置 · 内容预览 · 发布日历 · 素材管理   │
└──────────────────────┬───────────────────────────┘
                       │ HTTPS
┌──────────────────────▼───────────────────────────┐
│              API Gateway (Nginx/Kong)             │
│         认证 · 限流 · 日志 · 路由转发              │
└──────────────────────┬───────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────┐
│            Core Services (FastAPI)                │
│  ┌─────────────────────────────────────────────┐ │
│  │ 任务调度 (APScheduler)                      │ │
│  │ 提示词引擎 (Prompt Builder)                │ │
│  │ 内容编排器 (Content Orchestrator)          │ │
│  │ 去重引擎 (Dedup Engine)                    │ │
│  │ 资产管理器 (Asset Manager)                │ │
│  │ 社交发布器 (Social Publisher)             │ │
│  └─────────────────────────────────────────────┘ │
└──┬──────────┬──────────┬──────────┬──────────┬───┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
┌──────┐ ┌───────┐ ┌───────┐ ┌──────┐ ┌──────────┐
│Chroma│ │DeepSeek│ │Doubao │ │GitHub│ │ Buffer   │
│+CLIP │ │ API   │ │Seedream│ │API   │ │  API     │
└──────┘ └───────┘ └───────┘ └──────┘ └──────────┘
                      │
              ┌───────▼────────┐
              │ Redis + Celery │ (异步任务队列)
              └───────┬────────┘
                      ▼
              ┌───────────────┐
              │ PostgreSQL    │ (配置、日志、发布记录)
              └───────────────┘
```

---

## 3. 技术选型及版本

| 组件 | 选型 | 理由 |
|------|------|------|
| 后端框架 | FastAPI 0.110+ | 异步高性能，自带 OpenAPI 文档，便于对接 |
| 向量数据库 | Chroma 0.4.22 | 轻量级，支持自定义嵌入函数，与 Python 生态无缝 |
| 多模态嵌入 | openai/clip-vit-base-patch32 | 通过 HuggingFace 加载，图文向量对齐，开源成熟 |
| 文本生成 | DeepSeek API (deepseek-chat) | 中文能力强，成本可控，支持 16K 上下文 |
| 图像生成 | Doubao-Seedream-4.5 | 参考图输入支持好，画质适合商业摄影，火山引擎稳定 |
| 任务调度 | APScheduler 3.10 + Celery 5.3 | APScheduler 管理 Cron 触发；Celery 执行耗时任务 |
| 消息代理 | Redis 7 | Celery broker，同时用作缓存 |
| 数据库 | PostgreSQL 15 | 持久化任务配置、发布历史、操作日志 |
| 对象存储 | GitHub API + jsDelivr (主) ; Cloudflare R2 (备) | GitHub 免费 CDN 加速；R2 提供私有备份与高可用 |
| 社交分发 | Buffer API (Publish endpoint) | 统一管理三大平台，稳定官方接口 |
| 监控 | Prometheus + Grafana + Sentry | 指标采集、可视化、错误追踪 |

---

## 4. 核心模块详细设计

### 4.1 模块划分
| 模块 | 职责 |
|------|------|
| `knowledge_base` | 产品与图片子资源 CRUD，向量嵌入计算，元数据管理 |
| `prompt_builder` | 文案提示词动态构建，图像视觉规划生成 |
| `generator` | 调用 DeepSeek 与 Seedream-4.5，解析返回结果 |
| `dedup` | 图像感知哈希、CLIP 相似度、文案 MinHash 去重 |
| `asset_manager` | 上传图片至 GitHub 并获取 jsDelivr URL，备份至 R2 |
| `publisher` | Buffer API 封装，多平台发布与状态追踪 |
| `scheduler` | 定时任务解析、触发 Celery 异步链 |
| `api` | 对外 REST 接口聚合与鉴权 |

### 4.2 异步任务设计
所有耗时操作（图像生成、多张上传、去重计算）均通过 Celery 异步执行，任务链如下：

```
触发定时任务 → Celery Chain (
    生成文案任务,
    生成图像任务 (并行多张),
    去重验证任务,
    CDN上传任务,
    Buffer发布任务,
    更新知识库任务
) → 结果回调更新 PostgreSQL 状态
```

---

## 5. RESTful API 接口规范

### 5.1 通用规范
- Base URL: `https://api.bebcare-ai.com/v1`
- 认证：`Authorization: Bearer <JWT>`
- 所有时间采用 ISO 8601 格式。
- 列表接口支持 `?page=&size=` 分页。

### 5.2 产品知识库管理
#### 5.2.1 产品基本管理
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/products` | 创建新产品（仅基本信息） |
| GET | `/products/{product_id}` | 获取产品详情（含图片列表） |
| PUT | `/products/{product_id}` | 更新产品信息 |
| DELETE | `/products/{product_id}` | 删除产品及关联所有图片 |

**创建产品请求**：
```json
{
  "product_name": "Bebcare Linda 智能婴儿监视器",
  "category": "Bebcare Linda",
  "description": "无WiFi低辐射，哭声检测，室温显示...",
  "tags": ["baby", "monitor", "safety"],
  "brand_voice": "专业温暖"
}
```
**响应**：`201 Created`，返回 `product_id`。

#### 5.2.2 产品图片子资源管理
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/products/{product_id}/images` | 上传一张或多张图片 |
| GET | `/products/{product_id}/images` | 获取该产品所有图片元数据 |
| DELETE | `/products/{product_id}/images/{image_id}` | 删除指定图片 |

**上传图片请求**（multipart/form-data）：
```
files: [image1.jpg, image2.jpg]  # 字段名 'files'
```
可选 JSON 体（外部 URL）：
```json
{
  "image_urls": ["https://example.com/ref.jpg"]
}
```
**处理逻辑**：
1. 存储临时文件，计算 CLIP 嵌入和 pHash。
2. 上传至 GitHub 图床获得 jsDelivr CDN URL。
3. 将元数据（CDN URL、phash、embedding）存入 Chroma，关联 product_id。
4. 返回结果。

**响应**：
```json
{
  "product_id": "prod-123",
  "uploaded": [
    {
      "image_id": "img-uuid-1",
      "cdn_url": "https://cdn.jsdelivr.net/gh/user/repo@main/images/img1.jpg",
      "phash": "abc123...",
      "width": 1024,
      "height": 1024
    }
  ]
}
```

#### 5.2.3 获取产品详情（含图片列表）
`GET /products/{product_id}` 返回：
```json
{
  "product_id": "prod-123",
  "product_name": "...",
  "category": "...",
  "description": "...",
  "tags": [...],
  "images": [
    {
      "image_id": "img-uuid-1",
      "cdn_url": "...",
      "phash": "...",
      "uploaded_at": "2026-06-11T08:00:00Z"
    }
  ]
}
```

### 5.3 自动化任务配置
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/tasks` | 创建定时任务 |
| GET | `/tasks` | 任务列表 |
| GET | `/tasks/{task_id}` | 任务详情及最近执行日志 |
| PUT | `/tasks/{task_id}` | 修改任务 |
| DELETE | `/tasks/{task_id}` | 删除任务 |

**任务创建请求**：
```json
{
  "name": "每日Bebcare Linda发布",
  "cron": "0 10 * * *",
  "target_categories": ["Bebcare Linda"],
  "platforms": ["instagram", "tiktok", "facebook"],
  "reference_image_count": 3,
  "style": "random",
  "run_count_per_execution": 1,
  "enabled": true
}
```

### 5.4 手动生成与预览
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/generate` | 基于指定产品立即生成一组图文 |

**请求**：
```json
{
  "product_id": "prod-123",
  "platform": "instagram",
  "reference_count": 2,
  "style_hint": "storytelling"
}
```
**响应**：
```json
{
  "task_id": "celery-task-uuid",
  "status": "queued"
}
```
状态查询：`GET /tasks/{task_id}/status`

### 5.5 发布接口
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/publish` | 将指定图文立即发布到 Buffer |
| GET | `/publish/status/{publish_id}` | 查询发布状态 |

---

## 6. 提示词构建与内容生成引擎（核心优化）
完全摒弃静态模板，采用 **动态两阶段视觉推理 + 产品硬锚点** 策略，杜绝图文冲突。

### 6.1 文案提示词构建
- **输入**：从知识库获取的结构化产品画像（名称、卖点列表、目标受众、品牌调性）。
- **焦点轮换**：随机选中一个核心卖点（如“无辐射安全”）。
- **平台适配**：Instagram 精致、TikTok 活泼、Facebook 详实温暖。
- **风格注入**：从“痛点驱动”、“故事场景”、“功能亮点”、“社交证明”中随机选取。
- **系统提示词**：固定母婴营销专家角色。
- **用户提示词**：动态拼接上述元素，控制字数与 emoji 用量。
- **调用 DeepSeek**，温度 0.9，直接输出可发布文案。

### 6.2 图像提示词构建（两阶段动态生成）
#### 阶段一：视觉策略规划
调用 DeepSeek，输入产品外观特征、本次卖点、平台特性，强制输出 JSON：
```json
{
  "scene": "现代婴儿房一角，浅木色尿布台，晨光柔和",
  "lighting": "左侧窗自然光，暖色调，阴影干净",
  "composition": "中景，产品置于台面，微俯拍",
  "mood": "宁静、科技融入生活",
  "focus": "产品无天线设计、LED数显屏",
  "negative_elements": "WiFi图标、天线、路由器、杂乱物品"
}
```

#### 阶段二：提示词合成
- **产品硬锚点**：从知识库 `appearance` 字段（如“白色椭圆机身，木质底座”）固定前缀。
- **融合视觉大纲**：将 scene, lighting, composition, mood, focus 依次拼接。
- **画质强化**：添加 `8K, commercial photography, sharp focus`。
- **参考图色调匹配**：分析参考图平均 RGB，追加 `warm/cool color palette`。
- **负向提示词**：静态通用词 + 阶段一输出的 `negative_elements`。

### 6.3 图像生成与筛选
- 调用 Doubao-Seedream-4.5，传入合成 prompt、负向 prompt、N 张参考图（通过 IP-Adapter 风格约束）。
- 一次生成 4 张候选图，用 CLIP 计算每张图与文案主题的相似度，取最高分者。
- 支持手动设定生成数量与参考图数量（任务配置参数）。

---

## 7. 向量知识库设计

### 7.1 Chroma 集合
- **Collection name**: `bebcare_products`
- **Embedding function**: `HuggingFaceEmbedding('openai/clip-vit-base-patch32')` （仅对图像生成向量，文本存于 metadata）
- **Metadata schema**（每条记录对应一张图片）：
```json
{
  "product_id": "prod-123",
  "image_id": "img-uuid-1",
  "product_name": "Bebcare Linda",
  "category": "Bebcare Linda",
  "description": "...",
  "appearance": "白色椭圆机身，木质底座，无天线",
  "cdn_url": "https://cdn.jsdelivr.net/...",
  "phash": "abc123...",
  "embedding_model": "clip-vit-base-patch32",
  "tags": ["baby", "monitor"],
  "copywriting": "历史文案...",
  "created_at": "ISO"
}
```
- **索引**：基于 `category` 和 `product_id` 过滤查询。

---

## 8. 自动化调度与发布流程

### 8.1 定时触发
- APScheduler 解析用户配置的 Cron 表达式，到期触发 Celery 任务链。
- 任务链包含：
  1. 随机选取目标 category 下的一个产品。
  2. 随机选取 N 张该产品图片作为参考图。
  3. 并行调用文案生成与视觉规划。
  4. 合成图像 prompt 并生成 4 张候选图。
  5. 图像去重（L1: pHash, L2: CLIP 相似度），文案去重（MinHash）。
  6. 选取最佳图文对，上传图片至 GitHub 获取 CDN URL。
  7. 调用 Buffer 发布到指定社交平台。
  8. 将新图文写入知识库以扩充参考池。
  9. 记录执行日志至 PostgreSQL。

### 8.2 失败重试与降级
- 每个步骤失败自动重试 3 次（指数退避）。
- 若图像生成全部失败，降级为仅发布纯文案（可配置）。
- 所有异常通过 Sentry 报警，并记录在任务日志中。

---

## 9. 去重与质量保证

### 9.1 三层去重
- **L1 图像感知哈希**：与同 category 图片 pHash 汉明距离 ≤ 5 则判重。
- **L2 语义相似度**：新图与库内同产品图片的 CLIP 余弦相似度 > 0.92 则重生成。
- **L3 文案 MinHash**：Jaccard 相似度 > 0.8 则要求 DeepSeek 改写（最多 3 次）。

### 9.2 质量兜底
- 图文主题一致性：CLIP 图文匹配分数 < 0.25 则丢弃并重新生成。
- 敏感内容审核：基于关键词和开源 NSFW 模型过滤。

---


---

