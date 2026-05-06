import unittest

from app.discount import calculate_discount_plan_from_minutes


class DiscountPlanTests(unittest.TestCase):
    def assert_plan(self, elapsed, coupon_60, coupon_30, effective):
        plan = calculate_discount_plan_from_minutes(elapsed)
        self.assertEqual(plan.effective_minutes, effective)
        self.assertEqual(plan.coupon_60_count, coupon_60)
        self.assertEqual(plan.coupon_30_count, coupon_30)

    def test_boundary_rules_with_exit_buffer(self):
        self.assert_plan(0, 0, 1, 10)
        self.assert_plan(9, 0, 1, 19)
        self.assert_plan(10, 0, 1, 20)
        self.assert_plan(19, 0, 1, 29)
        self.assert_plan(20, 1, 0, 30)
        self.assert_plan(49, 1, 0, 59)
        self.assert_plan(50, 1, 1, 60)
        self.assert_plan(79, 1, 1, 89)
        self.assert_plan(80, 2, 0, 90)
        self.assert_plan(109, 2, 0, 119)
        self.assert_plan(110, 2, 1, 120)

    def test_three_hours_eleven_minutes(self):
        self.assert_plan(191, 3, 1, 201)

    def test_twenty_four_hour_cap(self):
        self.assert_plan(24 * 60, 24, 0, 24 * 60 + 10)


if __name__ == "__main__":
    unittest.main()
