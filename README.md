# BakeOven

烘焙占炉排程：发酵+烘烤半开区间占用炉位，冲突检测与下一可开工窗口。

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4500 |
| API | http://localhost:9500 |
| API 文档 | http://localhost:9500/docs |
| Postgres | localhost:5446 |

健康检查：`GET http://localhost:9500/api/health`

## 页面

- `/products` — 产品
- `/ovens` — 炉位
- `/batches` — 批次
- `/gantt` — 甘特
- `/conflicts` — 冲突
- `/windows` — 可开工

## 使用说明

1. 查看产品配方时长与炉位。
2. 创建生产批次，系统按半开区间占炉并检测冲突。
3. 甘特查看占用；冲突与可开工窗口辅助排产。

## 开发与测试

```bash
docker compose exec api pytest -q
```

## 数据校验与迁移

产品/批次共用一套时长与开工规则，应用层（422 并指明字段）与数据库 CHECK 约束双重执行：

- `ferment_min >= 0`（发酵分钟不得为负）
- `bake_min >= 1`（烘烤分钟至少为 1）
- `0 <= start_min < 1440`（开工分钟不得为负且小于一天的分钟数）

`POST /api/products` 创建产品；`POST /api/batches` 在重叠判断之前先校验 `start_min`。
迁移 `backend/migrations/001_add_duration_start_checks.sql` 幂等，随应用启动自动执行，也可手动执行：

```bash
docker compose exec api python -m app.services.migrate
```
