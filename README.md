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

1. 查看产品配方时长与炉位，可在产品页新增产品。
2. 创建生产批次，系统按半开区间占炉并检测冲突。
3. 甘特查看占用；冲突与可开工窗口辅助排产。

## 校验规则

产品与批次共用同一套时长/开工校验，应用层与数据库约束双重执行，报错均指明字段：

| 字段 | 规则 |
| --- | --- |
| `ferment_min` | 发酵分钟 ≥ 0 |
| `bake_min` | 烘烤分钟 ≥ 1 |
| `start_min` | 开工分钟 ≥ 0 且 < 1440（一天的分钟数） |

- 经 API 写入（`POST /api/products`、`POST /api/batches`）：非法值在进入重叠判断之前以 400 拒绝，报文含字段名，数据条数不变。
- 绕过应用直接写库：表的 CHECK 约束（`ck_products_*`、`ck_batches_*`）使插入失败，约束名含字段名。

## 数据库迁移

`backend/migrations/001_recipe_start_checks.sql` 为现有库补充上述 CHECK 约束，幂等、可重复执行；API 启动时会自动按序执行 `migrations/*.sql`（仅 Postgres）。现有种子数据（乡村欧包/黄油可颂/布朗尼与三批 BO 批次）均满足约束，迁移后照常启动，甘特色块不变。手动执行：

```bash
docker compose exec -T db psql -U bakeoven -d bakeoven < backend/migrations/001_recipe_start_checks.sql
```

## 开发与测试

```bash
docker compose exec api pytest -q
```
