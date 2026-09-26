"""Shared duration / start-minute rules for products and batches.

The same bounds are enforced twice:
- application layer: these helpers run before any scheduling logic and
  produce messages that name the offending field;
- database layer: CHECK constraints on the tables (see models.py and
  migrations/001_recipe_start_checks.sql) so direct writes bypassing the
  app fail too.
"""

MINUTES_PER_DAY = 24 * 60


def recipe_errors(ferment_min: int, bake_min: int) -> list[str]:
    """Validate product recipe durations; each error names its field."""
    errors: list[str] = []
    if ferment_min < 0:
        errors.append(f"ferment_min 发酵分钟不得为负（当前值 {ferment_min}）")
    if bake_min < 1:
        errors.append(f"bake_min 烘烤分钟至少为 1（当前值 {bake_min}）")
    return errors


def start_min_errors(start_min: int) -> list[str]:
    """Validate batch start minute within [0, MINUTES_PER_DAY)."""
    errors: list[str] = []
    if start_min < 0:
        errors.append(f"start_min 开工分钟不得为负（当前值 {start_min}）")
    if start_min >= MINUTES_PER_DAY:
        errors.append(
            f"start_min 开工分钟必须小于一天的分钟数 {MINUTES_PER_DAY}（当前值 {start_min}）"
        )
    return errors
