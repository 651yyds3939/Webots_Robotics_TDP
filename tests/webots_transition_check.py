"""Measure isolated transitions three times each; completion is not stability."""
import json
import math
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Base.SupervisorBase import SupervisorBase
from Utils.MatchEngine import MatchConfig
from Utils.CourseSpecs import TIME_STEP
from transition_cases import cases

s = SupervisorBase(MatchConfig(startup_seconds=0))
s.match.phase = 'SET'
receiver = s.getDevice('transition_receiver')
receiver.enable(TIME_STEP)
probe = s.robots['RedForwardA']
results = []
profile = os.environ.get('TDP_TRANSITION_PROFILE', 'isolated')
case_list = cases(profile)
if os.environ.get('TDP_TRANSITION_CASES'):
    selected = set(json.loads(os.environ['TDP_TRANSITION_CASES']))
    case_list = [case for case in case_list if case['name'] in selected]
repeats = int(os.environ.get('TDP_TRANSITION_REPEATS', '3'))


def step():
    if s.step(TIME_STEP) == -1:
        raise RuntimeError('Simulation stopped before measurements finished')
    s.sendSupervisorData()
    messages = []
    while receiver.getQueueLength():
        packet = json.loads(receiver.getString())
        receiver.nextPacket()
        if packet.get('kind') == 'transition_status':
            messages.append(packet)
    return messages


try:
    for repeat in range(1, repeats+1):
        for case in case_list:
            # Every case starts with a fresh physical state and fresh motion cache.
            for i, (name, node) in enumerate(s.robots.items()):
                node.loadState('kickoff')
                point = case.get('initial_position', [0, 0, .334]) if name == 'RedForwardA' else [-4 + .6*i, 2.5, .334]
                node.getField('translation').setSFVec3f(point)
                node.getField('rotation').setSFRotation([0, 0, 1, 0])
                node.resetPhysics()
                if name == 'RedForwardA':
                    node.restartController()
            s.setBallPosition(case.get('initial_ball', [-4.4, -2.8, .07]))
            for _ in range(40):
                step()
            while receiver.getQueueLength():
                receiver.nextPacket()
            start = list(probe.getPosition())
            yaw_start = float(s.getRobotAngle('RedForwardA'))
            started = s.getTime()
            s.log_file.write(json.dumps({'event': 'transition_fixture', 'time': started,
                                         'case': case['name'], 'repeat': repeat, 'segments': case['segments']})+'\n')
            s.emitter.send(json.dumps({'kind': 'transition_plan', 'case': case['name'],
                                      'repeat': repeat, 'segments': case['segments']}).encode())
            minimum_up, minimum_height, first_low = 1, start[2], None
            received_start, complete = None, None
            low_frames = 0
            for _ in range(sum(item['frames'] for item in case['segments']) + 25):
                messages = step()
                up, height = probe.getOrientation()[8], probe.getPosition()[2]
                minimum_up = min(minimum_up, up)
                minimum_height = min(minimum_height, height)
                if height < .20 and up < .5:
                    if first_low is None:
                        first_low = s.getTime() - started
                    low_frames += 1
                for packet in messages:
                    if packet['case'] == case['name'] and packet['repeat'] == repeat:
                        if packet['state'] == 'started':
                            received_start = packet['time']
                        elif packet['state'] == 'completed':
                            complete = packet['time']
                if complete is not None:
                    break
            if received_start is None or complete is None:
                raise RuntimeError(f'Transition probe failed to acknowledge {case["name"]}')
            end = list(probe.getPosition())
            result = {'case': case['name'], 'repeat': repeat, 'segments': case['segments'],
                      'profile': profile, 'ball_present': case.get('ball_present', False),
                      'initial_ball': case.get('initial_ball', [-4.4, -2.8, .07]),
                      'end_ball': list(s.ball.getPosition()),
                      'probe_started_time': received_start, 'probe_completed_time': complete,
                      'minimum_up': minimum_up, 'minimum_height': minimum_height,
                      'maximum_torso_tilt_rad': math.acos(max(-1, min(1, minimum_up))),
                      'low_tilted_frames': low_frames, 'low_tilted_observed': low_frames >= 3,
                      'first_low_tilted_seconds': first_low,
                      'displacement': [b-a for a, b in zip(start, end)],
                      'yaw_degrees': math.degrees((float(s.getRobotAngle('RedForwardA'))-yaw_start+math.pi)%(2*math.pi)-math.pi)}
            results.append(result)
            (s.log_directory/'transition-result.json').write_text(json.dumps(results, indent=2)+'\n')
            print('TRANSITION_MEASUREMENT', json.dumps(result), flush=True)
    print(f'TRANSITION_CHECK_OK: {len(results)} {profile} measurements completed; no stability or hardware claim', flush=True)
    s.step(TIME_STEP)
    s.simulationQuit(0)
except Exception:
    import traceback
    traceback.print_exc()
    s.step(TIME_STEP)
    s.simulationQuit(1)
