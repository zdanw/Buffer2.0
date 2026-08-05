# Bebcare AI Studio — 前端

管理后台：产品资产、提示词维度、定时任务、待发审核、发布日历、图像 Provider 与用户管理。

## 本地启动

需先启动后端（默认 `http://localhost:8080`，见 [backend/README.md](../backend/README.md)）。

```bash
cd frontend
npm ci
npm run dev    # http://localhost:5173
```

开发时浏览器请求同源相对路径 `/v1`，由 Vite 代理到 `http://localhost:8080`（`vite.config.ts`），**无需**配置 `VITE_*` 后端地址。

## 环境变量

模板见 `.env.example`。

| 场景 | 说明 |
|------|------|
| 本地 | 一般不用配；代理已写死到 `:8080` |
| Vercel | 配置 `HF_SPACE_HOST`（Space hostname，不要带 `https://`）；**不要**设置会打进前端包的 `VITE_BACKEND_URL` |

生产站点走 HTTPS，若前端包内写死 `http://*.hf.space` 会触发 Mixed Content 被浏览器拦截。`/v1` 由 `api/index.cjs`（Vercel）代理到 Space。

后端 `ALLOWED_ORIGINS` 须包含前端域名（逗号分隔白名单）。

## 常用脚本

```bash
npm run dev       # 开发
npm run build     # tsc + vite build
npm run preview   # 预览构建产物
npm run lint      # ESLint
```

要求 **Node 20.x**（见 `package.json` → `engines`）。

## 页面路由（摘要）

| 路由 | 模块 |
|------|------|
| `/login` | 登录 |
| `/assets` | 产品与参考图 |
| `/dimensions` | 提示词维度 |
| `/tasks` | 定时任务 |
| `/pending` | 待发审核（人工模式草稿） |
| `/preview` | 内容试生成 |
| `/calendar` | 发布日历 |
| `/image-models` | 图像 Provider（管理员） |
| `/users` | 用户管理（管理员） |

## 技术栈

React 19 · React Router 7 · Vite 6 · TypeScript · Tailwind CSS 3 · Axios · 部署：Vercel
