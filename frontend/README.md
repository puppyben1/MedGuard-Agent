# MedGuard-Agent 前端（React + Vite + TypeScript）

React 前端，通过 FastAPI 后端 API 调用 MedGuard-Agent 智能体。

## 快速启动

### 1. 启动后端（FastAPI）

在项目根目录：

```bash
# 安装后端依赖（首次）
pip install "fastapi>=0.115" "uvicorn[standard]>=0.30"

# 启动 API 服务（端口 8000）
uvicorn pharmagent.api.main:app --reload --port 8000
```

### 2. 启动前端（Vite 开发服务器）

在 `frontend/` 目录：

```bash
# 安装前端依赖（首次）
cd frontend
npm install

# 启动开发服务器（端口 5173）
npm run dev
```

打开浏览器访问：<http://localhost:5173>

Vite 会自动把 `/api/*` 请求代理到 <http://localhost:8000>。

### 3. 生产构建

```bash
cd frontend
npm run build      # 产物在 frontend/dist/
npm run preview    # 本地预览生产构建
```

## 架构

```
浏览器 ──http──▶ Vite Dev Server (5173)
                     │
                     │ /api/* 代理
                     ▼
                FastAPI (8000)
                     │
                     ├── /api/health        — 健康检查 + LLM 预算
                     ├── /api/prescription  — 处方审查
                     ├── /api/qa            — 药物安全问答
                     └── /api/examples      — 示例数据
                     │
                     ▼
              MedGuard-Agent 核心
              (LangGraph + RAG + 检索)
```

## 目录结构

```
frontend/
├── src/
│   ├── components/
│   │   ├── PrescriptionReview.tsx   # Tab 1: 处方审查
│   │   └── DrugSafetyQA.tsx         # Tab 2: 药物安全问答
│   ├── api.ts                       # API 客户端
│   ├── types.ts                     # TypeScript 类型（镜像后端 Pydantic）
│   ├── labels.ts                    # 中文标签映射
│   ├── App.tsx                      # 主应用
│   ├── main.tsx                     # 入口
│   └── index.css                    # Tailwind CSS
├── index.html
├── vite.config.ts                   # Vite 配置（含 /api 代理）
├── tsconfig.json
├── tailwind.config.js
└── package.json
```

## 环境变量

- `VITE_API_BASE`：API 基础路径。开发时留空（走 Vite 代理），生产部署时指向后端地址。

```bash
# 生产构建时指定后端地址
VITE_API_BASE=https://api.example.com npm run build
```
