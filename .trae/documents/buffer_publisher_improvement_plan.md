# Buffer 发布服务改进计划

## 一、需求分析

### 1.1 参考文件分析

参考文件 `buffer_service.py` 提供了以下核心功能：

| 组件 | 功能描述 | 关键特性 |
|------|----------|----------|
| PLATFORM_CONFIG | 平台配置映射 | 支持9+社交平台 |
| BufferGraphQLClient | GraphQL API客户端 | 支持账户信息、频道列表 |
| BufferCache | 缓存管理器 | TTL缓存策略 |

### 1.2 当前项目现状

当前 `buffer_publisher.py` 的局限性：

| 问题 | 影响 |
|------|------|
| 使用REST API | Buffer新版功能需要GraphQL |
| 无缓存机制 | 重复调用获取profile信息 |
| 有限平台支持 | 仅支持基础平台匹配 |

## 二、改进方案

### 2.1 改进内容

| 改进项 | 描述 | 状态 |
|--------|------|------|
| 平台配置 | 扩展支持9+社交平台 | ✅ |
| GraphQL API | 替换REST API为GraphQL | ✅ |
| 缓存机制 | 添加TTL缓存减少API调用 | ✅ |

**不包含以下功能**（按用户要求）：
- TikTok图片尺寸调整
- logging模块集成
- 自定义发布时间
- 多平台批量发布

### 2.2 文件修改

**修改文件**: `backend/bebcare/publisher/buffer_publisher.py`

**替换策略**: 保留原有 `buffer_publisher` 单例导出和 `publish` 方法签名

### 2.3 依赖检查

| 依赖 | 当前状态 | 是否需要新增 |
|------|----------|--------------|
| requests | ✅ 已安装 | 否 |

## 三、实施步骤

### 步骤1: 添加平台配置常量

定义 PLATFORM_CONFIG，包含各平台的服务名映射

### 步骤2: 实现 GraphQL 客户端

```python
class BufferGraphQLClient:
    - request(query, max_retries, initial_delay)
    - fetch_account_info()
    - fetch_channels(organization_id)
```

### 步骤3: 实现缓存管理器

```python
class BufferCache:
    - get_account_info(fetch_func)
    - get_channels(organization_id, fetch_func)
    - clear()
```

### 步骤4: 实现发布服务

```python
class BufferPublishService:
    - create_post(channel_id, text, media_url, platform_type)
    - publish_to_platforms(text, media_url, platforms)
```

### 步骤5: 保留兼容层

保持原有 `buffer_publisher` 单例和 `publish` 方法签名

## 四、风险评估

| 风险 | 等级 | 应对措施 |
|------|------|----------|
| GraphQL API兼容性 | 中 | 使用重试机制，捕获API错误 |
| 缓存数据过期 | 低 | 设置合理TTL(10分钟) |

## 五、测试验证

1. ✅ 服务启动时初始化正常
2. ✅ GraphQL API请求成功
3. ✅ 缓存机制生效
4. ✅ 发布功能正常
