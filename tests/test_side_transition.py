from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Wenao/controllers'))
from Utils.SideTransition import SideTransition


class SideTransitionTests(unittest.TestCase):
    def test_experiment_requires_actual_player_fixture_and_output(self):
        runner = Path(__file__).with_name('run_webots_check.py')
        for options in (['--attack'], ['--transitions', '--output', 'unused'],
                        ['--motions', '--output', 'unused']):
            result = subprocess.run([sys.executable, str(runner), '--side-transition', 'phase', *options],
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2, result.stderr)

    def request(self, gate, **values):
        arguments = dict(now=5., action='step_right', behaviour='DRIBBLE', current_action='walk',
                         phase_ms=840, duration_ms=960, motion_over=False)
        return gate.request(**{**arguments, **values})

    def test_default_off_does_not_intercept_late_side_request(self):
        gate = SideTransition()
        self.assertIsNone(self.request(gate))
        self.assertIsNone(gate.started)

    def test_only_late_dribble_walk_to_side_is_selected(self):
        for values in ({'behaviour': 'INTERCEPT'}, {'action': 'shoot'}, {'action': 'walk'},
                       {'current_action': 'step_left'}, {'phase_ms': 680}, {'duration_ms': 0}):
            self.assertIsNone(self.request(SideTransition('phase'), **values))
        self.assertEqual(self.request(SideTransition('phase'), phase_ms=720), 'begin')
        self.assertEqual(self.request(SideTransition('phase'), action='step_left'), 'begin')

    def test_settle_requires_elapsed_time_and_completed_stand(self):
        gate = SideTransition('phase')
        self.assertEqual(self.request(gate), 'begin')
        self.assertEqual(self.request(gate, now=6.16, current_action='stand', motion_over=True), 'wait')
        self.assertEqual(self.request(gate, now=6.20, current_action='stand', motion_over=False), 'wait')
        self.assertEqual(self.request(gate, now=6.20, current_action='stand', motion_over=True), 'release')
        self.assertIsNone(gate.started)
        self.assertIsNone(self.request(gate, now=6.24, current_action='stand', motion_over=True))

    def test_interruption_cancels_pending_settle(self):
        gate = SideTransition('phase')
        self.request(gate)
        self.assertIsNone(self.request(gate, current_action='recover_back'))
        self.assertIsNone(gate.started)
        self.request(gate)
        gate.cancel()
        self.assertIsNone(gate.started)


if __name__ == '__main__':
    unittest.main()
