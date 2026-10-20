from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Wenao/controllers'))
from Utils.GuardedLocomotion import GuardedLocomotion


class GuardedTests(unittest.TestCase):
    def test_strict_acceptance_requires_an_attack_and_output(self):
        runner = Path(__file__).with_name('run_webots_check.py')
        for options in (['--attack'], ['--match', '--output', 'unused']):
            result = subprocess.run([sys.executable, str(runner), '--require-no-fall', *options],
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2, result.stderr)

    def before(self, gate, now, **kwargs):
        values = dict(action='stand', over=True, phase_ms=1000, duration_ms=1000,
                      roll=0, pitch=.05, foot_z=[25, 25])
        return gate.before_decision(now, **{**values, **kwargs})

    def test_requires_persistent_double_support_after_motion_complete(self):
        gate = GuardedLocomotion(True)
        self.assertEqual(self.before(gate, 1), 'wait')
        self.assertEqual(self.before(gate, 1.04), 'wait')
        self.assertEqual(self.before(gate, 1.20), 'ready')
        self.assertEqual(self.before(gate, 1.24, foot_z=[-.7, 52]), 'wait')
        self.assertIsNone(gate.stable_since)

    def test_large_tilt_or_angular_velocity_resets_stability(self):
        gate = GuardedLocomotion(True)
        self.before(gate, 1)
        self.before(gate, 1.04)
        self.assertEqual(self.before(gate, 1.08, roll=.08), 'wait')
        self.assertIsNone(gate.stable_since)
        self.assertEqual(self.before(gate, 1.12, pitch=.2), 'wait')

    def test_requested_walking_stop_waits_for_actual_endpoint(self):
        gate = GuardedLocomotion(True)
        gate.stop_requested = True
        self.assertEqual(self.before(gate, 1, action='walk', phase_ms=840, duration_ms=960), 'wait')
        self.assertEqual(self.before(gate, 1.12, action='walk', phase_ms=960, duration_ms=960), 'settle')
        self.assertFalse(gate.stop_requested)

    def test_finished_side_motion_settles_before_new_decision(self):
        gate = GuardedLocomotion(True)
        self.assertEqual(self.before(gate, 1, action='step_left', over=False), 'wait')
        self.assertEqual(self.before(gate, 2, action='step_left', over=True), 'settle')


if __name__ == '__main__':
    unittest.main()
