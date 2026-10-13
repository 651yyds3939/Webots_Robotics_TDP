"""One real player must approach, advance and score; opponents stand aside."""
import json
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Base.SupervisorBase import SupervisorBase
from Utils.MatchEngine import MatchConfig
from Utils.CourseSpecs import TIME_STEP, goal_crossing

s = SupervisorBase(MatchConfig(startup_seconds=0))
s.match.phase = 'SET'
s.match.red_direction = 1
s.match.released = True
s.match.kickoff_restriction = False
try:
    for i, (name, node) in enumerate(s.robots.items()):
        point = [.5, -.15, .334] if name == 'RedForwardA' else [-4+.6*i, 2.5 if i%2 else -2.5, .334]
        node.getField('translation').setSFVec3f(point)
        node.getField('rotation').setSFRotation([0, 0, 1, 0])
        node.resetPhysics()
        node.restartController()
    s.setBallPosition([1.2, 0, .07])
    s.log_file.write(json.dumps({'event': 'attack_fixture', 'time': s.getTime(),
                                 'active_player': 'RedForwardA', 'initial_ball': [1.2, 0, .07]})+'\n')
    for _ in range(40):
        s.step(TIME_STEP)
        s.sendSupervisorData()
    s.match.phase = 'PLAYING'
    started = s.getTime()
    initial = list(s.ball.getPosition())
    previous = initial
    contacts = set()
    scored = False
    while s.getTime()-started < 180:
        if s.step(TIME_STEP) == -1:
            raise RuntimeError('Simulation stopped')
        touch = s.physical_touch()
        if touch:
            contacts.add(touch)
            s.match.last_touch = touch
        s.sendSupervisorData()
        current = list(s.ball.getPosition())
        scored = goal_crossing(previous, current) == 'RED'
        previous = current
        if scored:
            break
    result = {'scored': scored, 'seconds_to_end': s.getTime()-started,
              'start_ball': initial, 'end_ball': current, 'contacts': sorted(contacts),
              'opponents_active': False, 'success_rate_validated': False}
    (s.log_directory/'attack-result.json').write_text(json.dumps(result, indent=2))
    s.exportImage(str(s.log_directory/'attack-final.png'), 100)
    print('ATTACK_MEASUREMENT', json.dumps(result), flush=True)
    assert scored and 'RedForwardA' in contacts, result
    print('ATTACK_CHECK_OK: approach, advance and whole-ball goal in one unopposed fixture', flush=True)
    s.step(TIME_STEP)
    s.simulationQuit(0)
except Exception:
    import traceback
    traceback.print_exc()
    s.step(TIME_STEP)
    s.simulationQuit(1)
