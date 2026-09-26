-- 001_recipe_start_checks.sql
-- 为 products / batches 增加时长与开工分钟 CHECK 约束：
--   ferment_min >= 0, bake_min >= 1, 0 <= start_min < 1440
-- 约束名包含字段名，违反时可直接定位字段。
-- 幂等：可在现有库上重复执行；表不存在时（全新部署）跳过，
-- 新库由 ORM create_all 建表并自带同名约束。
-- 现有种子数据（乡村欧包 40/35、黄油可颂 25/20、布朗尼 0/30，
-- 批次开工 540/630/600）均满足上述约束，迁移可直接执行。
DO $$
BEGIN
  IF to_regclass('public.products') IS NOT NULL THEN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_products_ferment_min_gte_0') THEN
      ALTER TABLE products ADD CONSTRAINT ck_products_ferment_min_gte_0 CHECK (ferment_min >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_products_bake_min_gte_1') THEN
      ALTER TABLE products ADD CONSTRAINT ck_products_bake_min_gte_1 CHECK (bake_min >= 1);
    END IF;
  END IF;
  IF to_regclass('public.batches') IS NOT NULL THEN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_batches_start_min_gte_0') THEN
      ALTER TABLE batches ADD CONSTRAINT ck_batches_start_min_gte_0 CHECK (start_min >= 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_batches_start_min_lt_1440') THEN
      ALTER TABLE batches ADD CONSTRAINT ck_batches_start_min_lt_1440 CHECK (start_min < 1440);
    END IF;
  END IF;
END $$;
