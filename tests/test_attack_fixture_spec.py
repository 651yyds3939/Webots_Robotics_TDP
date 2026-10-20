import math
import unittest
from attack_fixture_spec import layout, no_fall_ok


class AttackFixtureTests(unittest.TestCase):
    def test_original_and_variations_change_actual_initial_geometry(self):
        own, ball, _ = layout('standard')
        self.assertEqual(own, [.5, -.15, .334])
        self.assertEqual(ball, [1.2, 0, .07])
        self.assertEqual(layout('mirrored')[0][1], -own[1])
        self.assertEqual(layout('offset')[1][1], .25)

    def test_strict_acceptance_rejects_falls_recovery_and_missing_measurements(self):
        self.assertTrue(no_fall_ok(.925, .287, 0))
        self.assertFalse(no_fall_ok(.925, .287, 1))
        self.assertFalse(no_fall_ok(.5, .287, 0))
        self.assertFalse(no_fall_ok(.925, .19, 0))
        for value in (math.nan, math.inf, -math.inf):
            self.assertFalse(no_fall_ok(value, .287, 0))
            self.assertFalse(no_fall_ok(.925, value, 0))


if __name__ == '__main__':
    unittest.main()
