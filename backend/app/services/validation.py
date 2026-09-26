"""Shared field validation for recipe durations and batch start minute.

Same rules as the database CHECK constraints (see models/migrations);
raising here keeps invalid writes from ever reaching conflict detection,
and the error always names the offending field.
"""

MINUTES_PER_DAY = 24 * 60


class FieldValidationError(ValueError):
    """A field failed validation; ``field`` names the offending field."""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


def validate_ferment_min(value: int) -> None:
    if value < 0:
        raise FieldValidationError("ferment_min", "发酵分钟不得为负（要求 ferment_min >= 0）")


def validate_bake_min(value: int) -> None:
    if value < 1:
        raise FieldValidationError("bake_min", "烘烤分钟至少为 1（要求 bake_min >= 1）")


def validate_start_min(value: int) -> None:
    if value < 0 or value >= MINUTES_PER_DAY:
        raise FieldValidationError(
            "start_min",
            f"开工分钟不得为负，且必须小于一天的分钟数 {MINUTES_PER_DAY}"
            f"（要求 0 <= start_min < {MINUTES_PER_DAY}）",
        )


def validate_recipe(ferment_min: int, bake_min: int) -> None:
    validate_ferment_min(ferment_min)
    validate_bake_min(bake_min)
