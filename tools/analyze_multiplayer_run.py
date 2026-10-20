"""Correlate multiplayer tilt episodes with sampled positions; proximity is not contact."""
import argparse
from bisect import bisect_right
from collections import Counter
from itertools import combinations
import json
import math
from pathlib import Path

from analyze_motion_diagnostics import summarize as summarize_motion


def records(paths):
    for path in sorted(paths):
        with path.open() as source:
            for line in source:
                if line.strip():
                    yield json.loads(line)


def summarize(directory):
    paths = list(directory.glob('match-*.jsonl'))
    if len(paths) != 1:
        raise ValueError('A separate directory containing exactly one match is required')
    match = list(records(paths))
    samples = sorted((r for r in match if r['event'] == 'sample'), key=lambda r: r['time'])
    if not samples:
        raise ValueError('No referee samples found')
    times = [r['time'] for r in samples]

    def observation(now):
        return samples[max(0, bisect_right(times, now)-1)]

    players = {}
    for name in samples[-1]['robots']:
        events = sorted(records(directory.glob(f'player-{name}-*.jsonl')), key=lambda r: r['time'])
        commands = [r for r in events if r['event'] == 'command']
        motion = summarize_motion(list(records(directory.glob(f'motion-{name}-*.jsonl'))), name)
        for episode in motion['tilt_episodes']:
            world = observation(episode['start_time'])
            own = world['robots'][name]['position']
            episode['phase'] = world['match']['phase']
            episode['half'] = world['match']['half']
            episode['reference_sample_age_seconds'] = episode['start_time']-world['time']
            episode['nearest_robots'] = sorted((
                {'robot': other, 'root_distance_metres': math.dist(own[:2], state['position'][:2])}
                for other, state in world['robots'].items() if other != name
            ), key=lambda r: r['root_distance_metres'])[:2]
        players[name] = {
            'commands': dict(Counter(r['action'] for r in commands)),
            'recovery_commands': [{'time': r['time'], 'action': r['action'],
                                   'phase': observation(r['time'])['match']['phase']}
                                  for r in commands if r['action'].startswith('recover')],
            'decision_transitions': dict(Counter(r['behaviour'] for r in events if r['event'] == 'decision')),
            'pass_intents_received': sum(r['event'] == 'pass_intent_received' for r in events),
            'motion': motion,
        }

    pair_seconds = Counter()
    for a, b in zip(samples, samples[1:]):
        if (a['match']['phase'] != 'PLAYING' or b['match']['phase'] != 'PLAYING'
                or a['match']['half'] != b['match']['half']):
            continue
        for left, right in combinations(a['robots'], 2):
            if left in a['penalties'] or right in a['penalties']:
                continue
            if math.dist(a['robots'][left]['position'][:2], a['robots'][right]['position'][:2]) < .30:
                pair_seconds[f'{left}/{right}'] += b['time']-a['time']

    manifest_path = directory/'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    return {
        'run': directory.name,
        'finished': samples[-1]['match']['phase'] == 'FINISHED',
        'last_time': samples[-1]['time'],
        'score': samples[-1]['match']['score'],
        'locomotion_mode': manifest.get('locomotion_mode'),
        'test_config': manifest.get('match_test_options'),
        'sample_count': len(samples),
        'players': players,
        'close_pair_threshold_metres': .30,
        'close_pair_seconds_sampled': dict(pair_seconds.most_common()),
        'referee_events': [r for r in match if r['event'] in
                           ('goal', 'restart', 'penalty', 'penalty_end', 'setup_removal', 'fixture_formation')],
        'limitations': [
            'Tilt threshold crossings and recovery commands are not validated physical fall counts.',
            'Root-node proximity and adjacent motion transitions do not prove collision or causation.',
            'Neighbour positions use the latest preceding referee sample, not an exact contact frame.',
            'Close-pair durations are sampled approximations, not contact durations.',
            'Command and pass-intent counts are attempts, not successful shots or passes.',
            'Referee and fixture placements are not autonomous locomotion.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = json.dumps(summarize(args.run), indent=2, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report+'\n')
    print(report)


if __name__ == '__main__':
    main()
