"""Fixed, no-ball experiments; all durations are integer 40 ms steps."""
import json
from pathlib import Path


def segment(action, seconds, phase_ms=None, repeat=False):
    frames = round(seconds / .04)
    if frames <= 0 or abs(frames * .04 - seconds) > 1e-9:
        raise ValueError('Duration must be a positive multiple of 40 ms')
    result = {'action': action, 'frames': frames, 'repeat': repeat}
    if phase_ms is not None:
        result['phase_ms'] = phase_ms
    return result


def cases(profile='isolated'):
    if profile == 'replay':
        return replay_cases()
    if profile != 'isolated':
        raise ValueError('Unknown transition profile')
    right, left = segment('step_right', 1.56), segment('step_left', 1.56)
    settle = segment('stand', 1.2)
    result = [
        {'name': 'walk_only', 'segments': [segment('walk', 8)]},
        {'name': 'right_only', 'segments': [segment('step_right', 8, repeat=True)]},
        {'name': 'left_only', 'segments': [segment('step_left', 8, repeat=True)]},
        {'name': 'right_left_direct', 'segments': [right, left]},
        {'name': 'right_stand_left', 'segments': [right, settle, left]},
    ]
    for phase in (0, 480, 840):
        walk = segment('walk', 1, phase_ms=phase)
        for transition, middle in [('direct', []), ('stand', [settle])]:
            result.append({'name': f'walk_phase{phase}_{transition}_right_left',
                           'segments': [walk, *middle, right, left]})
    # Hold the last target for one second to observe late instability.
    for case in result:
        case['segments'] = [*case['segments'], {'action': 'hold', 'frames': 25}]
    return result


def replay_cases():
    trace = json.loads(Path(__file__).with_name('transition_replay.json').read_text())
    result = []
    for ball in ('present', 'absent'):
        for mode in ('direct', 'stand'):
            plan = []
            for item in trace['segments']:
                if item.get('recorded_time') == 48.04 and mode == 'stand':
                    plan.append(segment('stand', 1.2))
                plan.append(dict(item))
            result.append({'name': f'replay_ball_{ball}_{mode}', 'segments': plan,
                           'initial_position': [.5, -.15, .334],
                           'initial_ball': [1.2, 0, .07] if ball == 'present' else [-4.4, -2.8, .07],
                           'ball_present': ball == 'present'})
    return result


def active_segment(segments, frame):
    """A boundary belongs to the next segment; None means the plan is finished."""
    end = 0
    for index, item in enumerate(segments):
        end += item['frames']
        if frame < end:
            return index
    return None
