"""Summarize measured tilt episodes and the transitions immediately before them."""
import argparse
import json
import math
from pathlib import Path


def summarize(rows, robot):
    rows = sorted((r for r in rows if r.get('robot') == robot), key=lambda r: r['time'])
    episodes, transitions = [], []
    above = False
    samples = 0
    last_transition = None
    for row in rows:
        if row.get('event') == 'motion_transition_before':
            last_transition = {k: row.get(k) for k in ('time', 'action', 'requested_action',
                                                       'motion_time_ms', 'motion_duration_ms')}
            transitions.append(last_transition)
        if row.get('event') != 'motion_sample':
            continue
        samples += 1
        rpy = row.get('imu_rpy', [])
        if len(rpy) != 3 or any(v is None or not math.isfinite(v) for v in rpy):
            above = False
            continue
        tilted = max(abs(rpy[0]), abs(rpy[1])) > .8
        if tilted and not above:
            errors = {name: abs(v['error']) for name, v in row.get('joints', {}).items()
                      if v.get('error') is not None}
            worst = max(errors, key=errors.get) if errors else None
            episodes.append({'start_time': row['time'], 'end_time': row['time'],
                             'action_at_threshold': row['action'], 'imu_rpy_at_threshold': rpy,
                             'motion_time_ms': row['motion_time_ms'],
                             'motion_duration_ms': row['motion_duration_ms'],
                             'preceding_transition': last_transition,
                             'reference_position': row.get('reference_position'),
                             'foot_force_local': row.get('foot_force_local'),
                             'largest_joint_error': {'joint': worst, 'radians': errors[worst]} if worst else None})
        elif tilted:
            episodes[-1]['end_time'] = row['time']
        above = tilted
    return {'robot': robot, 'sample_count': samples, 'tilt_threshold_rad': .8,
            'tilt_episodes': episodes, 'transition_count': len(transitions),
            'limitations': ['Tilt episodes are threshold crossings, not a validated count of physical falls.',
                            'Foot forces use sensor-local axes; no support-state calibration is applied.',
                            'Joint tracking error and adjacent transitions do not establish causation.',
                            'Reference positions come from referee localization.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--robot', default='RedForwardA')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    paths = sorted(args.run.glob(f'motion-{args.robot}-*.jsonl'))
    if not paths:
        parser.error('No diagnostic logs found; run with --diagnostics first')
    rows = [json.loads(line) for path in paths for line in path.read_text().splitlines() if line.strip()]
    report = summarize(rows, args.robot)
    if not report['sample_count']:
        parser.error('No diagnostic samples found for this robot')
    text = json.dumps(report, indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + '\n')
    print(text)


if __name__ == '__main__':
    main()
