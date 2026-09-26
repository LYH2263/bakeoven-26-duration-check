-- 001_add_duration_start_checks.sql
-- 为产品与批次补上时长/开工校验的数据库约束（与 app.models.models 中的
-- CheckConstraint 同名，因此对已有库幂等，可重复执行）：
--   products.ferment_min >= 0            发酵分钟不得为负
--   products.bake_min    >= 1            烘烤分钟至少为 1
--   batches.start_min    in [0, 1440)    开工分钟不得为负且小于一天的分钟数
-- 现有种子数据（乡村欧包 40/35、黄油可颂 25/20、布朗尼 0/30，
-- 批次开工 540/630/600）均满足约束，迁移可直接在现有库上执行。

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_products_ferment_min_nonnegative'
    ) THEN
        ALTER TABLE products
            ADD CONSTRAINT ck_products_ferment_min_nonnegative
            CHECK (ferment_min >= 0);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_products_bake_min_positive'
    ) THEN
        ALTER TABLE products
            ADD CONSTRAINT ck_products_bake_min_positive
            CHECK (bake_min >= 1);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_batches_start_min_within_day'
    ) THEN
        ALTER TABLE batches
            ADD CONSTRAINT ck_batches_start_min_within_day
            CHECK (start_min >= 0 AND start_min < 1440);
    END IF;
END $$;
