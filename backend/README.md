---
title: Bebcare AI Studio API
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: docker
sdk_version: 4.36.1
app_file: app.py
---

# Bebcare AI Studio API

全自动社媒内容生成与发布系统后端服务

## 启动方式

```bash
uvicorn app:app --host 0.0.0.0 --port 7860
```

## 环境变量

```env
# 数据库配置
DATABASE_URL=sqlite:///./bebcare.db

# DeepSeek API配置
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_API_URL=https://api.deepseek.com/v1

# Doubao API配置
DOUBAO_API_KEY=your_doubao_api_key
DOUBAO_API_URL=https://ark.cn-beijing.volces.com/api/v3/images/generations
DOUBAO_MODEL_ID=your_model_id

# Buffer API配置
BUFFER_API_TOKEN=your_buffer_api_token

# GitHub图床配置
GITHUB_TOKEN=your_github_token
GITHUB_USERNAME=your_github_username
GITHUB_REPO=your_github_repo
GITHUB_BRANCH=main

# 安全配置
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# 管理员账户配置（可选）
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@bebcare.com
ADMIN_PASSWORD=  # 留空则自动生成随机密码

# 应用配置
APP_HOST=0.0.0.0
APP_PORT=7860
LOG_LEVEL=INFO
```

## API 接口

- `POST /api/auth/login` - 用户登录
- `GET /api/auth/me` - 获取当前用户信息
- `GET /api/auth/users` - 获取用户列表
- `POST /api/auth/users` - 创建用户
- `PUT /api/auth/users/{user_id}` - 更新用户
- `DELETE /api/auth/users/{user_id}` - 删除用户

## 技术栈

- FastAPI 0.110.0
- Uvicorn
- SQLAlchemy 2.0
- ChromaDB
- PyTorch
- Transformers