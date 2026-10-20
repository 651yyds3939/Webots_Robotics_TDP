"""One real player must approach, advance and score; opponents stand aside."""
import json
import math
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Base.SupervisorBase import SupervisorBase
from Utils.MatchEngine import MatchConfig
from Utils.CourseSpecs import TIME_STEP, goal_crossing
from attack_fixture_spec import layout, no_fall_ok

s = SupervisorBase(MatchConfig(startup_seconds=0))
s.match.phase = 'SET'
s.match.red_direction = 1
s.match.released = True
s.match.kickoff_restriction = False
layout_name = os.environ.get('TDP_ATTACK_LAYOUT', 'standard')
initial_robot, initial_ball, initial_yaw = layout(layout_name)
try:
    for i, (name, node) in enumerate(s.robots.items()):
        point = initial_robot if name == 'RedForwardA' else [-4+.6*i, 2.5 if i%2 else -2.5, .334]
        node.getField('translation').setSFVec3f(point)
        node.getField('rotation').setSFRotation([0, 0, 1, initial_yaw if name == 'RedForwardA' else 0])
        node.resetPhysics()
        node.restartController()
    s.setBallPosition(initial_ball)
    s.log_file.write(json.dumps({'event': 'attack_fixture', 'time': s.getTime(),
                                 'active_player': 'RedForwardA', 'initial_ball': initial_ball,
                                 'initial_robot': initial_robot, 'layout': layout_name})+'\n')
    for _ in range(40):
        s.step(TIME_STEP)
        s.sendSupervisorData()
    s.match.phase = 'PLAYING'
    started = s.getTime()
    initial = list(s.ball.getPosition())
    previous = initial
    contacts = set()
    scored = False
    own_robot = s.robots['RedForwardA']
    minimum_up, minimum_height = 1., float('inf')
    while s.getTime()-started < 180:
        if s.step(TIME_STEP) == -1:
            raise RuntimeError('Simulation stopped')
        touch = s.physical_touch()
        if touch:
            contacts.add(touch)
            s.match.last_touch = touch
        s.sendSupervisorData()
        current = list(s.ball.getPosition())
        minimum_up = min(minimum_up, own_robot.getOrientation()[8])
        minimum_height = min(minimum_height, own_robot.getPosition()[2])
        scored = goal_crossing(previous, current) == 'RED'
        previous = current
        if scored:
            break
    elapsed = s.getTime()-started
    strict = os.environ.get('TDP_ATTACK_NO_FALL') == '1'
    if scored and strict:
        # Test stopping after the goal as well, rather than hiding a late fall.
        s.match.phase = 'FINISHED'
        for _ in range(40):
            if s.step(TIME_STEP) == -1:
                raise RuntimeError('Simulation stopped during post-goal stability check')
            s.sendSupervisorData()
            minimum_up = min(minimum_up, own_robot.getOrientation()[8])
            minimum_height = min(minimum_height, own_robot.getPosition()[2])
    recovery_attempts = 0
    for path in s.log_directory.glob('player-RedForwardA-*.jsonl'):
        for line in path.read_text().splitlines():
            row = json.loads(line)
            recovery_attempts += int(row['event'] == 'command' and row.get('action', '').startswith('recover'))
    no_fall = no_fall_ok(minimum_up, minimum_height, recovery_attempts)
    result = {'scored': scored, 'seconds_to_end': elapsed,
              'layout': layout_name, 'initial_robot': initial_robot,
              'start_ball': initial, 'end_ball': current, 'contacts': sorted(contacts),
              'minimum_up': minimum_up, 'maximum_torso_tilt_radians': math.acos(max(-1., min(1., minimum_up))),
              'minimum_torso_height': minimum_height, 'recovery_attempts': recovery_attempts,
              'no_fall_criterion_passed': no_fall, 'strict_no_fall_required': strict,
              'post_goal_seconds': 1.6 if scored and strict else 0,
              'opponents_active': False, 'success_rate_validated': False}
    (s.log_directory/'attack-result.json').write_text(json.dumps(result, indent=2))
    s.exportImage(str(s.log_directory/'attack-final.png'), 100)
    print('ATTACK_MEASUREMENT', json.dumps(result), flush=True)
    assert scored and 'RedForwardA' in contacts, result
    if strict:
        assert no_fall, result
    print('ATTACK_CHECK_OK: approach, advance and whole-ball goal in one unopposed fixture', flush=True)
    s.step(TIME_STEP)
    s.simulationQuit(0)
except Exception:
    import traceback
    traceback.print_exc()
    s.step(TIME_STEP)
    s.simulationQuit(1)
