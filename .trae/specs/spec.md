# Bebcare 全自动社媒内容生成与发布系统 - Product Requirement Document

## Overview
- **Summary**: 构建一个基于AI的端到端自动化内容工厂，实现从知识库提取、智能创作、去重校验到多平台发布的闭环。系统将集成DeepSeek文案生成、Doubao-Seedream-4.5图像生成、Chroma向量数据库、GitHub+jsDelivr图床以及Buffer社交分发平台。
- **Purpose**: 解决Bebcare母婴硬件品牌在TikTok、Instagram、Facebook持续产出高质量视觉图文的需求，提升内容创作效率和一致性。
- **Target Users**: Bebcare品牌营销团队、内容运营人员

## Goals
- 建立多模态向量知识库，存储产品图像、文案与元数据
- 构建动态提示词系统，驱动AI文案和图像生成
- 实现三层去重保障内容原创性
- 集成GitHub+jsDelivr图床与Buffer社交分发
- 提供用户可配置的全自动定时任务，零人工干预
- 提供React前端界面，支持任务配置、内容预览、发布日历和素材管理

## Non-Goals (Out of Scope)
- 不实现用户认证系统（假设已存在）
- 不支持其他社交媒体平台（仅限TikTok、Instagram、Facebook）
- 不提供图片编辑功能

## Background & Context
Bebcare母婴硬件品牌当前面临人工创作效率低、风格波动大的问题。急需一套基于AI的自动化内容生产系统，实现：
1. 产品知识的结构化存储与检索
2. 基于产品特性的智能文案生成
3. 与文案匹配的高质量图像生成
4. 内容去重与质量保证
5. 自动化多平台发布

## Functional Requirements
- **FR-1**: 产品知识库管理 - 支持产品CRUD操作，包含基本信息和关联图片
- **FR-2**: 产品图片子资源管理 - 支持图片上传、存储、向量嵌入计算
- **FR-3**: 自动化任务配置 - 支持定时任务创建、修改、删除和状态查询
- **FR-4**: 手动生成与预览 - 支持基于指定产品立即生成图文内容
- **FR-5**: 发布接口 - 支持将图文内容发布到Buffer平台
- **FR-6**: 提示词构建引擎 - 动态生成文案和图像提示词
- **FR-7**: AI内容生成 - 调用DeepSeek和Doubao-Seedream-4.5生成内容
- **FR-8**: 三层去重机制 - 图像感知哈希、CLIP语义相似度、文案MinHash去重
- **FR-9**: 自动化调度 - APScheduler定时触发+Celery异步任务链执行
- **FR-10**: React前端界面 - 任务配置、内容预览、发布日历、素材管理

## Non-Functional Requirements
- **NFR-1**: 性能 - 图像生成响应时间<30秒，文案生成<10秒
- **NFR-2**: 可靠性 - 任务失败自动重试3次（指数退避）
- **NFR-3**: 可观测性 - 集成Prometheus+Grafana+Sentry监控
- **NFR-4**: 安全性 - API认证使用JWT，敏感数据加密存储
- **NFR-5**: 可扩展性 - 模块化设计，支持新增平台和模型

## Constraints
- **Technical**: Python 3.10+, FastAPI, Chroma, Redis, PostgreSQL
- **Business**: 依赖外部API（DeepSeek、Doubao、Buffer）
- **Dependencies**: 需要配置API密钥（DeepSeek、Doubao、Buffer、GitHub）

## Assumptions
- 已存在JWT认证系统
- 外部API服务可用且稳定
- 网络连接正常，可访问外部服务
- 用户熟悉CRON表达式配置

## Acceptance Criteria

### AC-1: 产品创建成功
- **Given**: 系统正常运行，用户提供有效的产品数据
- **When**: POST /products 发送有效的产品信息
- **Then**: 返回201 Created状态码和product_id
- **Verification**: `programmatic`

### AC-2: 产品图片上传成功
- **Given**: 产品已存在，用户上传有效图片文件
- **When**: POST /products/{product_id}/images 上传图片
- **Then**: 图片成功存储到GitHub图床，返回CDN URL和元数据
- **Verification**: `programmatic`

### AC-3: 定时任务创建成功
- **Given**: 用户提供有效的CRON表达式和配置参数
- **When**: POST /tasks 创建定时任务
- **Then**: 任务成功注册到APScheduler，返回task_id
- **Verification**: `programmatic`

### AC-4: 手动生成图文内容
- **Given**: 指定产品存在且有参考图片
- **When**: POST /generate 请求生成内容
- **Then**: 返回Celery任务ID，异步执行生成流程
- **Verification**: `programmatic`

### AC-5: 内容发布到Buffer
- **Given**: 图文内容已生成，Buffer API配置正确
- **When**: POST /publish 发布内容
- **Then**: 内容成功提交到Buffer，返回publish_id
- **Verification**: `programmatic`

### AC-6: 图像去重检测
- **Given**: 新生成图像与知识库中图像相似
- **When**: 去重引擎处理图像
- **Then**: pHash汉明距离≤5或CLIP相似度>0.92时判定为重复
- **Verification**: `programmatic`

### AC-7: 文案去重检测
- **Given**: 新生成文案与历史文案相似
- **When**: 去重引擎处理文案
- **Then**: MinHash Jaccard相似度>0.8时触发重新生成（最多3次）
- **Verification**: `programmatic`

### AC-8: 图文主题一致性校验
- **Given**: 生成的图文对
- **When**: 质量保证模块校验
- **Then**: CLIP图文匹配分数<0.25时丢弃并重新生成
- **Verification**: `programmatic`

### AC-9: 定时任务执行成功
- **Given**: 定时任务已启用且配置正确
- **When**: CRON表达式触发时间到达
- **Then**: Celery任务链完整执行，内容成功发布到指定平台
- **Verification**: `programmatic`

### AC-10: 失败重试与降级
- **Given**: 图像生成失败
- **When**: 自动重试3次后仍失败
- **Then**: 降级为仅发布纯文案（可配置）
- **Verification**: `programmatic`

## Resolved Questions
- API密钥管理：DeepSeek、Doubao、Buffer的API密钥以及GitHub图床配置（用户名、仓库名、分支）均通过环境变量进行管理
- 存储方案：不支持Cloudflare R2作为备选存储，仅使用GitHub+jsDelivr
- 监控系统：不部署Prometheus+Grafana+Sentry监控系统
