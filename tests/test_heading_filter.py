import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Wenao/controllers'))
from Utils.HeadingFilter import HeadingFilter, turn_threshold


class HeadingTests(unittest.TestCase):
    def test_wrap_boundary_does_not_invent_a_half_turn(self):
        heading = HeadingFilter()
        heading.update(math.radians(179), 0)
        value = heading.update(math.radians(-179), .04)
        self.assertLess(abs(abs(value)-math.pi), math.radians(2))

    def test_gait_sway_is_filtered_but_a_real_turn_is_followed(self):
        heading = HeadingFilter()
        heading.update(0, 0)
        values = [heading.update(math.radians(16 if i % 2 else -16), i*.04) for i in range(1, 51)]
        self.assertLess(max(abs(v) for v in values), math.radians(12))
        for i in range(51, 81):
            value = heading.update(math.pi/2, i*.04)
        self.assertLess(abs(value-math.pi/2), math.radians(1))
        self.assertGreater(turn_threshold(True, True), turn_threshold(True, False))
        self.assertEqual(turn_threshold(False, True), 12)
