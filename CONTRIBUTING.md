# Contributing Guide

本项目用于团队协作开发，提交前请遵循以下规范。

## 分支策略

- `main`：稳定分支，不直接在本分支开发。
- `feature/<name>`：新功能开发。
- `fix/<name>`：缺陷修复。
- `docs/<name>`：文档改动。

## 提交规范

建议使用 Conventional Commits：

- `feat:` 新功能
- `fix:` 问题修复
- `refactor:` 重构
- `docs:` 文档更新
- `chore:` 工程维护

示例：

```text
feat(frontend): add websocket fallback polling for async fraud task
```

## Pull Request 要求

- 说明变更背景和目标。
- 列出主要改动点。
- 附上验证方式（命令、截图、接口回包等）。
- 如涉及配置，说明新增环境变量。

## 提交前检查

后端最小校验：

```bash
python -m py_compile backend/app.py
```

前端最小校验：

```bash
cd frontend
npm run build
```

## 不应提交的文件

以下内容属于运行时或构建产物，不应提交：

- 本地数据库：`*.db`
- 运行日志：`logs/`
- 前端构建产物：`frontend/dist/`
- 依赖缓存：`frontend/node_modules/`
- 临时目录和 pid：`.tmp/`、`.pids/`
- RAG 自动构建产物：`config/data/knowledge/raw/`、`config/data/knowledge/processed/`、`config/data/knowledge/index/`
