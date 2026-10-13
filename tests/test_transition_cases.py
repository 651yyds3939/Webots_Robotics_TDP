import unittest
from pathlib import Path
import subprocess
import sys
from transition_cases import cases, segment, active_segment


class TransitionCaseTests(unittest.TestCase):
    def test_invalid_selection_is_rejected_before_launch(self):
        runner = Path(__file__).with_name('run_webots_check.py')
        for options in (['--transitions', '--output', 'unused', '--transition-case', 'missing'],
                        ['--transitions', '--output', 'unused', '--transition-repeats', '0'],
                        ['--transition-case', 'walk_only']):
            result = subprocess.run([sys.executable, str(runner), *options],
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2, result.stderr)

    def test_exact_boundary_selects_next_segment_and_end_finishes(self):
        plan = [segment('walk', 1), segment('stand', 1.2)]
        self.assertEqual(active_segment(plan, 24), 0)
        self.assertEqual(active_segment(plan, 25), 1)
        self.assertIsNone(active_segment(plan, 55))

    def test_matrix_changes_only_stand_transition_for_each_phase(self):
        plans = {case['name']: case['segments'] for case in cases()}
        self.assertEqual(len(plans), 11)
        for phase in (0, 480, 840):
            direct = plans[f'walk_phase{phase}_direct_right_left']
            settled = plans[f'walk_phase{phase}_stand_right_left']
            self.assertEqual(direct, [settled[0], *settled[2:]])
            self.assertEqual(settled[1]['action'], 'stand')
            self.assertEqual(direct[0]['phase_ms'], phase)

    def test_fractional_frame_cannot_silently_change_schedule(self):
        with self.assertRaises(ValueError):
            segment('walk', .05)
        with self.assertRaises(ValueError):
            segment('walk', 0)

    def test_replay_preserves_recorded_timing_and_only_inserts_one_stand(self):
        plans = {case['name']: case for case in cases('replay')}
        self.assertEqual(len(plans), 4)
        direct = plans['replay_ball_present_direct']['segments']
        absent = plans['replay_ball_absent_direct']['segments']
        self.assertEqual(direct, absent)
        elapsed = 1.64
        for item in direct:
            if 'recorded_time' in item:
                self.assertAlmostEqual(elapsed, item['recorded_time'])
            elapsed += item['frames'] * .04
        settled = plans['replay_ball_present_stand']['segments']
        inserted = [i for i, item in enumerate(settled) if item['action'] == 'stand']
        self.assertEqual(len(inserted), 1)
        i = inserted[0]
        self.assertEqual(settled[i+1]['recorded_time'], 48.04)
        self.assertEqual(direct, settled[:i] + settled[i+1:])


if __name__ == '__main__':
    unittest.main()
