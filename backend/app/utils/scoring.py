from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.models.enums import UomType


def _pct(value: Decimal) -> Decimal:
    """Clamp value to [0, 100] and round to 2 decimal places."""
    bounded = max(Decimal("0"), min(value, Decimal("100")))
    return bounded.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_progress_score(
    uom_type: UomType,
    target_value: Decimal | None,
    actual_value: Decimal | None,
    target_date: date | None,
    completion_date: date | None,
) -> Decimal | None:
    """
    Compute a 0–100 progress score based on Unit of Measure type.

    NUMERIC_MAX / PERCENTAGE_MAX:
        Maximize output — higher actual is better.
        Score = (actual / target) × 100.
        Example: target=100 units, actual=80 → score=80.00

    NUMERIC_MIN / PERCENTAGE_MIN:
        Minimize waste — lower actual is better.
        Score = (target / actual) × 100, capped at 100.
        Example: target=10 defects, actual=5 → score=100.00 (over-performed)

    ZERO:
        Binary — score=100 if actual==0 else 0.

    TIMELINE:
        Binary — score=100 if completed on or before target date else 0.
    """
    if uom_type in {UomType.NUMERIC_MAX, UomType.PERCENTAGE_MAX}:
        # Higher actual = better. Guard against zero target.
        if target_value is None or target_value == 0 or actual_value is None:
            return None
        return _pct((actual_value / target_value) * Decimal("100"))

    if uom_type in {UomType.NUMERIC_MIN, UomType.PERCENTAGE_MIN}:
        # Lower actual = better. Guard against zero actual (perfect score).
        if actual_value is None or target_value is None:
            return None
        if actual_value == 0:
            return Decimal("100.00")  # zero actual on a minimize goal = perfect
        return _pct((target_value / actual_value) * Decimal("100"))

    if uom_type == UomType.ZERO:
        if actual_value is None:
            return None
        return Decimal("100.00") if actual_value == 0 else Decimal("0.00")

    if uom_type == UomType.TIMELINE:
        if not target_date or not completion_date:
            return None
        return Decimal("100.00") if completion_date <= target_date else Decimal("0.00")

    return None

