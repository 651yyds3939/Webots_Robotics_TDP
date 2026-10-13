import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Wenao/controllers'))
from Utils.Navigation import Navigator
from Utils.TeamPolicy import Decision, TeamPolicy
from test_match_behaviours import world


class NavigationTests(unittest.TestCase):
    def test_sideways_error_is_not_corrected_with_a_half_turn(self):
        d = Decision('SHOOT', (-.17, -.05), (4.5, 0), 'shoot')
        action, stage = Navigator().choose(d, [-.17, -.18], 0, [0, 0])
        self.assertEqual((action, stage), ('step_left', 'ALIGN_FOOT_LATERALLY'))

    def test_body_frame_alignment_is_symmetric_at_both_ends(self):
        for yaw, own, goal in [(0, [-.18, -.05], (4.5, 0)), (math.pi, [.18, .05], (-4.5, 0))]:
            d = Decision('SHOOT', tuple(own), goal, 'shoot')
            self.assertEqual(Navigator().choose(d, own, yaw, [0, 0])[0], 'shoot')

    def test_dribble_advances_instead_of_turning_toward_point_under_body(self):
        d = Decision('DRIBBLE', (-.19, 0), (1, 0))
        nav = Navigator()
        self.assertEqual(nav.choose(d, [-.19, -.04], 0, [0, 0]), ('walk', 'DRIBBLE_TOWARD_GOAL'))
        self.assertEqual(nav.choose(d, [-.05, 0], 0, [0, 0]), ('back', 'MAKE_FOOT_SPACE'))

    def test_front_side_approach_routes_around_the_ball(self):
        d = Decision('INTERCEPT', (-.19, 0), (1, 0))
        action, stage = Navigator().choose(d, [.5, 0], math.pi, [0, 0])
        self.assertEqual(stage, 'APPROACH_BEHIND_BALL')
        self.assertNotEqual(action, 'walk')

    def test_role_position_hysteresis_ignores_small_pose_sway(self):
        d = Decision('SUPPORT', (0, 0), (4, 0))
        nav = Navigator()
        self.assertEqual(nav.choose(d, [.05, 0], 0, [1, 0])[0], 'stand')
        self.assertEqual(nav.choose(d, [.20, 0], 0, [1, 0])[0], 'stand')
        self.assertNotEqual(nav.choose(d, [.5, 0], 0, [1, 0])[0], 'stand')

    def test_clear_is_forward_even_beyond_midfield(self):
        w = world()
        policy = TeamPolicy('RedDefender')
        d = policy.attack([2.5, 0], [2.8, 0], 1, {}, [])
        self.assertGreater(d.face[0], 2.8)

    def test_shared_last_touch_keeps_carrier_through_small_distance_changes(self):
        w = world()
        w['robots']['RedForwardA']['position'] = [-.25, 0, .334]
        w['robots']['RedForwardB']['position'] = [-.20, 0, .334]
        w['match']['last_touch'] = 'RedForwardA'
        self.assertEqual(TeamPolicy('RedForwardA').decide(w).behaviour, 'DRIBBLE')
        self.assertEqual(TeamPolicy('RedForwardB').decide(w).behaviour, 'SUPPORT')

    def test_wide_dribble_aims_inside_goal_aperture(self):
        d = TeamPolicy('RedForwardA').attack([3.2, 2.5], [3.5, 2.5], 1, {}, [])
        self.assertEqual(d.behaviour, 'DRIBBLE')
        self.assertEqual(d.face, (4.5, .9))
