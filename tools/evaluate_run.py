"""Summarize measured evidence; command counts are never labelled successes."""
import argparse
from collections import Counter
import json
import math
import statistics
from pathlib import Path


def summarize(directory):
    if len(list(directory.glob('match-*.jsonl'))) > 1:
        raise ValueError('Multiple matches found; evaluate a separate directory for each run')
    records = []
    for source in sorted(directory.glob('*.jsonl')):
        for line in source.read_text().splitlines():
            records.append(json.loads(line))
    samples = sorted((r for r in records if r['event'] == 'sample'), key=lambda r: r['time'])
    commands = Counter(r['action'] for r in records if r['event'] == 'command')
    decisions = Counter(r['behaviour'] for r in records if r['event'] == 'decision')
    goals = Counter(r['team'] for r in records if r['event'] == 'goal')
    falls = Counter(r['robot'] for r in records if r['event'] == 'penalty' and r['reason'] == 'fallen')
    placements = [r['time'] for r in records if r['event'] == 'place_ball' and 'time' in r]
    ball_path = sum(math.dist(a['ball']['position'][:2], b['ball']['position'][:2]) for a, b in zip(samples, samples[1:])
                    if a['match']['phase'] == b['match']['phase'] == 'PLAYING'
                    and not any(a['time'] <= t <= b['time'] for t in placements))
    touches = Counter()
    previous_touch = None
    for sample in samples:
        touch = sample['match']['last_touch']
        if touch and touch != previous_touch:
            touches[touch] += 1
        previous_touch = touch
    playing_seconds = sum(b['time']-a['time'] for a, b in zip(samples, samples[1:])
                          if a['match']['phase'] == b['match']['phase'] == 'PLAYING')
    setup_removals = Counter(r['robot'] for r in records if r['event'] == 'setup_removal')
    fixtures = [r['time'] for r in records if r['event'] == 'fixture_formation']
    removals = [r for r in records if r['event'] in ('penalty', 'penalty_end', 'setup_removal')]
    locomotion = Counter()
    for a, b in zip(samples, samples[1:]):
        if a['match']['phase'] != 'PLAYING' or b['match']['phase'] != 'PLAYING':
            continue
        for name in a['robots']:
            # Include only unpenalized continuous motion; exclude referee/fixture teleports.
            removed = any(r.get('robot') == name and r['event'] in ('penalty', 'penalty_end', 'setup_removal')
                          and a['time'] <= r['time'] <= b['time'] for r in removals)
            if (name in a['penalties'] or name in b['penalties'] or removed
                    or any(a['time'] <= t <= b['time'] for t in placements+fixtures)):
                continue
            locomotion[name] += math.dist(a['robots'][name]['position'][:2], b['robots'][name]['position'][:2])
    command_seconds = Counter()
    walk_bouts = []
    for name in {r['robot'] for r in records if r['event'] == 'command'}:
        events = sorted((r for r in records if r['event'] == 'command' and r['robot'] == name), key=lambda r: r['time'])
        for a, b in zip(events, events[1:]):
            command_seconds[a['action']] += b['time']-a['time']
            if a['action'] == 'walk':
                walk_bouts.append(b['time']-a['time'])
    return {'sample_count': len(samples), 'last_time': samples[-1]['time'] if samples else None,
            'last_phase': samples[-1]['match']['phase'] if samples else None,
            'playing_seconds_sampled': playing_seconds, 'setup_removals': dict(setup_removals),
            'fixture_formation_count': len(fixtures),
            'robot_path_metres_sampled': dict(locomotion),
            'command_seconds_all_phases': dict(command_seconds),
            'median_walk_bout_seconds': statistics.median(walk_bouts) if walk_bouts else None,
            'commands': dict(commands), 'decision_transitions': dict(decisions),
            'goals': dict(goals), 'fallen_removal_penalties': dict(falls),
            'contact_transitions': dict(touches), 'ball_path_metres_sampled': ball_path,
            'limitations': ['Commands are attempts, not successful behaviours.',
                            'Ball path excludes logged referee placements; unlogged fixture movements are not match performance.',
                            'Contact attribution uses Webots contact-location approximation.',
                            'Robot path includes torso sway; it is not calibrated forward speed.',
                            'Command durations include READY and recovery; they are not skill success times.',
                            'No hardware or calibrated-vision accuracy demonstrated.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = json.dumps(summarize(args.directory), indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result+'\n')
    print(result)
