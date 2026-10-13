"""Measure raw motion speed/rotation before choosing a locomotion profile."""
import json
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Base.SupervisorBase import SupervisorBase
from Utils.MatchEngine import MatchConfig
from Utils.CourseSpecs import TIME_STEP

s = SupervisorBase(MatchConfig(startup_seconds=0))
s.match.phase = 'SET'
probe = s.robots['RedForwardA']
results = []
try:
    for action in ('walk', 'dribble', 'sprint', 'back', 'step_left', 'step_right', 'left10', 'right10', 'left20', 'right20', 'left40', 'right40'):
        probe.loadState('kickoff')
        probe.getField('translation').setSFVec3f([0, 0, .334])
        probe.getField('rotation').setSFRotation([0, 0, 1, 0])
        probe.resetPhysics()
        probe.restartController()
        s.setBallPosition([-4.4, -2.8, .07])
        for _ in range(40):
            s.step(TIME_STEP)
            s.sendSupervisorData()
        start = list(probe.getPosition())
        yaw_start = float(s.getRobotAngle('RedForwardA'))
        s.emitter.send(json.dumps({'kind': 'motion_probe', 'action': action}).encode())
        duration = 4 if action.startswith(('left', 'right')) else 8
        minimum_up = 1
        for _ in range(round(duration*1000/TIME_STEP)):
            s.step(TIME_STEP)
            s.sendSupervisorData()
            minimum_up = min(minimum_up, probe.getOrientation()[8])
        end = list(probe.getPosition())
        yaw = float(s.getRobotAngle('RedForwardA'))
        result = {'action': action, 'seconds': duration, 'displacement': [b-a for a, b in zip(start, end)],
                  'forward_metres_per_second': (end[0]-start[0])/duration,
                  'yaw_degrees': math.degrees((yaw-yaw_start+math.pi)%(2*math.pi)-math.pi),
                  'minimum_up': minimum_up, 'end_height': end[2]}
        results.append(result)
        print('MOTION_MEASUREMENT', json.dumps(result), flush=True)
    (s.log_directory/'motion-result.json').write_text(json.dumps(results, indent=2))
    print('MOTION_CHECK_OK: measurements only; no hardware calibration', flush=True)
    s.step(TIME_STEP)
    s.simulationQuit(0)
except Exception:
    import traceback
    traceback.print_exc()
    s.step(TIME_STEP)
    s.simulationQuit(1)
