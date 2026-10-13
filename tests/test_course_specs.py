"""Boundary and calibration checks; run with Python 3.10 in robotics-tdp."""
import importlib
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Wenao/controllers"))
from Utils.CourseSpecs import goal_crossing
from Utils.pathPlanning import aStar
import numpy as np


class GoalTests(unittest.TestCase):
    def test_ball_must_cross_wholly_and_only_once(self):
        self.assertIsNone(goal_crossing([4.49, 0, .07], [4.51, 0, .07]))
        self.assertEqual(goal_crossing([4.56, 0, .07], [4.58, 0, .07]), "RED")
        self.assertIsNone(goal_crossing([4.58, 0, .07], [4.60, 0, .07]))
        self.assertIsNone(goal_crossing([4.60, 0, .07], [4.56, 0, .07]))

    def test_both_ends_and_wider_goal(self):
        self.assertEqual(goal_crossing([-4.56, 1, .07], [-4.58, 1, .07]), "BLUE")
        self.assertEqual(goal_crossing([4.56, 1, .07], [4.58, 1, .07]), "RED")

    def test_ball_must_fit_between_posts_and_under_bar(self):
        self.assertIsNone(goal_crossing([4.56, 1.24, .07], [4.58, 1.24, .07]))
        self.assertIsNone(goal_crossing([4.56, 0, 1.14], [4.58, 0, 1.14]))
        self.assertIsNone(goal_crossing([4.56, 0, 2], [4.58, 0, 2]))

    def test_uses_crossing_location_not_end_of_step(self):
        self.assertEqual(goal_crossing([4.56, 0, .07], [4.60, 2, .07]), "RED")
        self.assertIsNone(goal_crossing([4.56, 2, .07], [4.60, 0, .07]))


class PlanningTests(unittest.TestCase):
    def test_rectangular_grid_and_path_order(self):
        grid = np.zeros((3, 8))
        grid[1, 2:6] = 1
        path = aStar(grid, (0, 1), (7, 1))
        self.assertEqual(path[-1], (7, 1))
        previous = (0, 1)
        self.assertEqual(len(path), 9)
        for x, y in path:
            self.assertEqual(abs(x-previous[0]) + abs(y-previous[1]), 1)
            self.assertEqual(grid[y, x], 0)
            previous = (x, y)

    def test_outside_grid_and_no_path(self):
        grid = np.zeros((3, 8))
        self.assertFalse(aStar(grid, (-1, 0), (1, 0)))
        self.assertFalse(aStar(grid, (0, 0), (8, 0)))
        grid[:, 3] = 1
        self.assertFalse(aStar(grid, (0, 0), (7, 0)))


class VisionTests(unittest.TestCase):
    def test_camera_calibration_and_mixed_csv_records(self):
        module = importlib.import_module("Utils.ImageServer")
        class Camera:
            def getFov(self):
                return .982620
        with patch.object(module, "YOLO"), patch.object(module, "Thread"):
            server = module.ImageServer(640, 480, Camera(), "Test", "Top")
        # A distant, on-axis ball should agree with pinhole projection.
        width_at_two_metres = .14 * (640 / (2*math.tan(.982620/2))) / 2
        self.assertAlmostEqual(server.ball_distance(width_at_two_metres), 2)
        self.assertAlmostEqual(server.ball_heading(320, 240), 0)
        self.assertAlmostEqual(server.ball_heading(640, 240), math.degrees(.982620/2))
        with tempfile.TemporaryDirectory() as directory:
            server.log_path = Path(directory) / "vision.csv"
            server.save_data_to_csv()
            self.assertIn("distance_estimate", server.log_path.read_text())
            self.assertEqual(len(server.log_path.read_text().splitlines()), 4)


if __name__ == "__main__":
    unittest.main()
