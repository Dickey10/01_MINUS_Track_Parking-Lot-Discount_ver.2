from dataclasses import dataclass
from datetime import datetime
import math


EXIT_BUFFER_MINUTES = 10


@dataclass(frozen=True)
class DiscountPlan:
    elapsed_minutes: int
    effective_minutes: int
    coupon_30_count: int
    coupon_60_count: int
    total_discount_minutes: int


def calculate_discount_plan(entry_time: datetime, now: datetime | None = None) -> DiscountPlan:
    """Calculate parking coupons using a 10-minute exit buffer and 60-minute priority."""
    current = now or datetime.now(entry_time.tzinfo)
    elapsed = max(0, math.ceil((current - entry_time).total_seconds() / 60))
    effective = elapsed + EXIT_BUFFER_MINUTES
    units_30 = max(1, math.floor((effective + 10) / 30) + 1)
    coupon_60 = units_30 // 2
    coupon_30 = units_30 % 2
    return DiscountPlan(
        elapsed_minutes=elapsed,
        effective_minutes=effective,
        coupon_30_count=coupon_30,
        coupon_60_count=coupon_60,
        total_discount_minutes=(coupon_60 * 60) + (coupon_30 * 30),
    )


def calculate_discount_plan_from_minutes(elapsed_minutes: int) -> DiscountPlan:
    effective = max(0, elapsed_minutes) + EXIT_BUFFER_MINUTES
    units_30 = max(1, math.floor((effective + 10) / 30) + 1)
    coupon_60 = units_30 // 2
    coupon_30 = units_30 % 2
    return DiscountPlan(
        elapsed_minutes=max(0, elapsed_minutes),
        effective_minutes=effective,
        coupon_30_count=coupon_30,
        coupon_60_count=coupon_60,
        total_discount_minutes=(coupon_60 * 60) + (coupon_30 * 30),
    )
