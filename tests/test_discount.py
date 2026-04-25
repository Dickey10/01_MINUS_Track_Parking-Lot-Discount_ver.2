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
        self.assert_plan(10, 1, 0, 20)
        self.assert_plan(39, 1, 0, 49)
        self.assert_plan(40, 1, 1, 50)
        self.assert_plan(69, 1, 1, 79)
        self.assert_plan(70, 2, 0, 80)
        self.assert_plan(99, 2, 0, 109)
        self.assert_plan(100, 2, 1, 110)


if __name__ == "__main__":
    unittest.main()

