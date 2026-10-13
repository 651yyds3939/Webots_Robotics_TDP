"""Group fixture measurements; completion and sampled low poses are distinct."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path


def summarize(results):
    grouped = defaultdict(list)
    for row in results:
        grouped[row['case']].append(row)
    cases = {}
    for name, rows in grouped.items():
        tilts = [math.degrees(row['maximum_torso_tilt_rad']) for row in rows]
        yaw = [row['yaw_degrees'] for row in rows]
        cases[name] = {'measurement_count': len(rows),
                       'low_tilted_observed_count': sum(row['low_tilted_observed'] for row in rows),
                       'maximum_torso_tilt_degrees_range': [min(tilts), max(tilts)],
                       'yaw_degrees_range': [min(yaw), max(yaw)],
                       'minimum_height_metres': min(row['minimum_height'] for row in rows)}
    return {'measurement_count': len(results), 'cases': cases,
            'limitations': ['Low tilted observation requires at least three samples with torso height < 0.20 m and up < 0.5; samples need not be consecutive.',
                            'Cases replay motor commands; tactical decisions and automatic recovery are disabled.',
                            'Identical-condition repeats demonstrate repeatability, not a general success probability.',
                            'Stand transitions add time and change subsequent physical state.',
                            'Torso tilt uses acos of model up-axis; it is not identical to per-axis IMU thresholds.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    path = args.run / 'transition-result.json'
    if not path.exists():
        parser.error('No transition-result.json found')
    results = json.loads(path.read_text())
    if not results:
        parser.error('No completed measurements found')
    text = json.dumps(summarize(results), indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + '\n')
    print(text)


if __name__ == '__main__':
    main()
