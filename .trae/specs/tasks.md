# Bebcare 全自动社媒内容生成与发布系统 - Implementation Plan

## [x] Task 1: 项目基础设施搭建
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 创建项目目录结构
  - 配置Python虚拟环境
  - 安装核心依赖（FastAPI、Chroma、Celery、APScheduler等）
  - 创建配置文件管理（环境变量、API密钥）
- **Acceptance Criteria Addressed**: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10]
- **Test Requirements**:
  - `programmatic` TR-1.1: 项目目录结构正确创建
  - `programmatic` TR-1.2: 所有依赖成功安装
  - `human-judgement` TR-1.3: 配置文件结构清晰，密钥管理安全

## [x] Task 2: 数据库与向量库配置
- **Priority**: P0
- **Depends On**: Task 1
- **Description**: 
  - 配置PostgreSQL连接和表结构（任务配置、发布记录、操作日志）
  - 初始化Chroma向量数据库
  - 配置CLIP多模态嵌入函数
  - 创建向量库collection和metadata schema
- **Acceptance Criteria Addressed**: [AC-1, AC-2]
- **Test Requirements**:
  - `programmatic` TR-2.1: PostgreSQL表结构创建成功
  - `programmatic` TR-2.2: Chroma collection创建成功
  - `programmatic` TR-2.3: CLIP嵌入函数加载正常

## [x] Task 3: 产品知识库管理模块
- **Priority**: P0
- **Depends On**: Task 2
- **Description**: 
  - 实现产品CRUD操作
  - 实现图片上传与处理
  - 集成GitHub图床上传获取CDN URL
  - 计算图像CLIP嵌入和pHash
  - 将元数据存入Chroma向量库
- **Acceptance Criteria Addressed**: [AC-1, AC-2]
- **Test Requirements**:
  - `programmatic` TR-3.1: POST /products 创建产品成功，返回201
  - `programmatic` TR-3.2: GET /products/{product_id} 返回产品详情含图片列表
  - `programmatic` TR-3.3: POST /products/{product_id}/images 上传图片成功，返回CDN URL
  - `programmatic` TR-3.4: 图片元数据正确存入Chroma

## [x] Task 4: 提示词构建引擎
- **Priority**: P0
- **Depends On**: Task 2
- **Description**: 
  - 实现文案提示词动态构建（产品画像、焦点轮换、平台适配、风格注入）
  - 实现图像提示词两阶段生成（视觉策略规划+提示词合成）
  - 支持平台差异化（Instagram/TikTok/Facebook）
  - 实现参考图色调分析与匹配
- **Acceptance Criteria Addressed**: [AC-4, AC-8]
- **Test Requirements**:
  - `programmatic` TR-4.1: 文案提示词正确生成，包含产品信息和平台适配
  - `programmatic` TR-4.2: 图像提示词包含scene、lighting、composition等字段
  - `human-judgement` TR-4.3: 生成的提示词质量高，符合营销文案规范

## [x] Task 5: AI内容生成模块
- **Priority**: P0
- **Depends On**: Task 4
- **Description**: 
  - 集成DeepSeek API调用（文案生成）
  - 集成Doubao-Seedream-4.5 API调用（图像生成）
  - 实现一次生成4张候选图并选取最佳
  - 实现CLIP图文匹配评分
- **Acceptance Criteria Addressed**: [AC-4, AC-8]
- **Test Requirements**:
  - `programmatic` TR-5.1: DeepSeek文案生成成功
  - `programmatic` TR-5.2: Doubao图像生成成功，返回4张候选图
  - `programmatic` TR-5.3: CLIP图文匹配评分正确计算

## [x] Task 6: 三层去重引擎
- **Priority**: P0
- **Depends On**: Task 2, Task 5
- **Description**: 
  - 实现L1: 图像pHash感知哈希去重（汉明距离≤5判重）
  - 实现L2: CLIP语义相似度去重（余弦相似度>0.92判重）
  - 实现L3: 文案MinHash去重（Jaccard相似度>0.8触发改写）
  - 实现图文主题一致性校验（CLIP匹配分数<0.25丢弃）
- **Acceptance Criteria Addressed**: [AC-6, AC-7, AC-8]
- **Test Requirements**:
  - `programmatic` TR-6.1: pHash去重正确检测相似图像
  - `programmatic` TR-6.2: CLIP相似度去重正确检测相似图像
  - `programmatic` TR-6.3: MinHash文案去重正确检测相似文案
  - `programmatic` TR-6.4: 图文匹配分数<0.25时正确丢弃

## [x] Task 7: Buffer社交发布模块
- **Priority**: P0
- **Depends On**: Task 3, Task 5
- **Description**: 
  - 集成Buffer API
  - 实现多平台发布（Instagram、TikTok、Facebook）
  - 实现发布状态追踪
  - 实现发布记录持久化到PostgreSQL
- **Acceptance Criteria Addressed**: [AC-5]
- **Test Requirements**:
  - `programmatic` TR-7.1: POST /publish 成功提交到Buffer
  - `programmatic` TR-7.2: GET /publish/status/{publish_id} 返回正确状态
  - `programmatic` TR-7.3: 发布记录正确存入PostgreSQL

## [x] Task 8: Celery异步任务链
- **Priority**: P0
- **Depends On**: Task 3, Task 5, Task 6, Task 7
- **Description**: 
  - 配置Celery与Redis
  - 实现生成文案任务
  - 实现生成图像任务（并行多张）
  - 实现去重验证任务
  - 实现CDN上传任务
  - 实现Buffer发布任务
  - 实现任务链编排
- **Acceptance Criteria Addressed**: [AC-4, AC-5, AC-9, AC-10]
- **Test Requirements**:
  - `programmatic` TR-8.1: Celery任务成功入队
  - `programmatic` TR-8.2: 任务链按顺序执行
  - `programmatic` TR-8.3: 失败重试机制正常工作（指数退避3次）

## [x] Task 9: APScheduler定时任务
- **Priority**: P0
- **Depends On**: Task 8
- **Description**: 
  - 配置APScheduler
  - 实现定时任务CRUD接口
  - 实现CRON表达式解析与验证
  - 实现任务触发Celery异步链
  - 实现任务启用/禁用功能
- **Acceptance Criteria Addressed**: [AC-3, AC-9]
- **Test Requirements**:
  - `programmatic` TR-9.1: POST /tasks 创建定时任务成功
  - `programmatic` TR-9.2: CRON表达式正确解析
  - `programmatic` TR-9.3: 定时任务正确触发Celery任务

## [x] Task 10: REST API接口聚合
- **Priority**: P0
- **Depends On**: Task 3, Task 7, Task 8, Task 9
- **Description**: 
  - 创建FastAPI应用
  - 聚合所有模块API
  - 实现JWT认证中间件
  - 实现请求限流
  - 添加OpenAPI文档
- **Acceptance Criteria Addressed**: [AC-1, AC-2, AC-3, AC-4, AC-5]
- **Test Requirements**:
  - `programmatic` TR-10.1: 所有API端点正确注册
  - `programmatic` TR-10.2: JWT认证正常工作
  - `programmatic` TR-10.3: OpenAPI文档可访问

## [x] Task 11: React前端界面开发
- **Priority**: P0
- **Depends On**: Task 10
- **Description**: 
  - 创建React项目结构（使用Vite + TypeScript）
  - 实现任务配置模块（定时任务CRUD、CRON表达式编辑器）
  - 实现内容预览模块（图文内容展示、生成状态查看）
  - 实现发布日历模块（发布历史、即将发布任务）
  - 实现素材管理模块（产品列表、图片上传）
  - 配置API请求代理
- **Acceptance Criteria Addressed**: [AC-1, AC-2, AC-3, AC-4, AC-5]
- **Test Requirements**:
  - `programmatic` TR-11.1: 前端项目构建成功
  - `human-judgement` TR-11.2: 任务配置界面功能完整
  - `human-judgement` TR-11.3: 内容预览界面美观且功能正常
  - `human-judgement` TR-11.4: 发布日历展示清晰
  - `human-judgement` TR-11.5: 素材管理界面功能完整

## [x] Task 12: 测试与验证
- **Priority**: P0
- **Depends On**: All previous tasks
- **Description**: 
  - 编写单元测试（各模块独立功能）
  - 编写集成测试（端到端流程）
  - 验证所有API接口
  - 验证去重算法准确性
- **Acceptance Criteria Addressed**: [所有AC]
- **Test Requirements**:
  - `programmatic` TR-12.1: 单元测试覆盖率≥80%
  - `programmatic` TR-12.2: 集成测试覆盖核心流程
  - `programmatic` TR-12.3: 所有API接口测试通过
