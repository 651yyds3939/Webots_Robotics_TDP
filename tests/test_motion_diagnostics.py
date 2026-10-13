import importlib.util
import json
import math
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Wenao/controllers'))
from Utils.MotionDiagnostics import MotionDiagnostics, finite

spec = importlib.util.spec_from_file_location('analyze_motion', ROOT / 'tools/analyze_motion_diagnostics.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


class DiagnosticsTests(unittest.TestCase):
    def test_nonfinite_startup_values_are_json_null(self):
        self.assertEqual(finite({'a': [math.nan, math.inf, -.2]}), {'a': [None, None, -.2]})

    def test_snapshot_reads_actual_motion_time_and_joint_tracking(self):
        enabled = []
        sensor = SimpleNamespace(enable=enabled.append, getValue=lambda: .3)
        motor = SimpleNamespace(getTargetPosition=lambda: .5)
        class ForcePointer:
            def __iter__(self):
                raise AssertionError('Force pointer must be read with a bounded slice')

            def __getitem__(self, key):
                if key != slice(None, 3):
                    raise AssertionError('Exactly three force components are required')
                return [0, 1, 20]
        foot = SimpleNamespace(enable=enabled.append, getValues=lambda: ForcePointer())
        robot = SimpleNamespace(getName=lambda: 'RedForwardA', getTime=lambda: 2.0)
        imu = SimpleNamespace(getRollPitchYaw=lambda: [0, -.9, 0])
        motion = SimpleNamespace(getTime=lambda: 520, getDuration=lambda: 960, isOver=lambda: False)
        owner = SimpleNamespace(current=motion, current_action='walk', current_behaviour='DRIBBLE',
                                navigation_stage='TEST', observation=SimpleNamespace(world=None))
        with tempfile.TemporaryDirectory() as directory:
            logger = MotionDiagnostics(robot, {'LHipPitch': motor, 'LHipPitchS': sensor, 'LFsr': foot},
                                       imu, Path(directory), 40)
            logger.ready = True
            logger.snapshot(owner)
            logger.close()
            rows = [json.loads(line) for line in next(Path(directory).glob('*.jsonl')).read_text().splitlines()]
        self.assertEqual(enabled, [40, 40])
        row = rows[-1]
        self.assertEqual(row['motion_time_ms'], 520)
        self.assertAlmostEqual(row['joints']['LHipPitch']['error'], .2)
        self.assertEqual(row['foot_force_local']['LFsr'], [0, 1, 20])

    def test_two_recovery_commands_with_continuous_tilt_are_one_episode(self):
        def sample(t, pitch):
            return {'event': 'motion_sample', 'robot': 'R', 'time': t, 'action': 'recover_back',
                    'imu_rpy': [0, pitch, 0], 'motion_time_ms': 80, 'motion_duration_ms': 3400}
        rows = [sample(1, 0), {'event': 'motion_transition_before', 'robot': 'R', 'time': 1.5,
                               'action': 'step_right', 'requested_action': 'step_left'},
                sample(2, -1), sample(3, -1.2), sample(4, 0), sample(5, -.9)]
        report = analysis.summarize(rows, 'R')
        self.assertEqual(len(report['tilt_episodes']), 2)
        self.assertEqual(report['tilt_episodes'][0]['end_time'], 3)
        self.assertEqual(report['tilt_episodes'][0]['preceding_transition']['requested_action'], 'step_left')


if __name__ == '__main__':
    unittest.main()
