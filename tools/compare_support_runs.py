"""Validate and compare a completed Webots support experiment and its baseline."""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path

from analyze_multiplayer_run import summarize


def read_run(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    result = json.loads((directory / "integration-result.json").read_text())
    if "FINISHED" not in result["phases"]:
        raise ValueError(f"Incomplete match: {directory}")
    modes = defaultdict(set)
    for path in directory.glob("player-*.jsonl"):
        for line in path.open():
            record = json.loads(line)
            if record.get("event") == "command":
                modes[record["robot"]].add(record.get("support_mode"))
    analysis = summarize(directory)
    with next(directory.glob("match-*.jsonl")).open() as stream:
        samples = {r["time"]: r for line in stream if (r := json.loads(line)).get("event") == "sample"}
    summary = {"score_red_blue": result["score"], "simulated_seconds": result["simulated_seconds"],
        "playing_seconds": result["playing_seconds"],
        "recovery_commands": sum(len(p["recovery_commands"]) for p in analysis["players"].values()),
        "tilt_episodes": sum(len(p["motion"]["tilt_episodes"]) for p in analysis["players"].values()),
        "close_pair_seconds": sum(analysis["close_pair_seconds_sampled"].values()),
        "actual_modes": {n: sorted(v, key=str) for n, v in sorted(modes.items())}}
    summary["recovery_commands_per_playing_minute"] = summary["recovery_commands"]/(result["playing_seconds"]/60)
    return manifest, summary, samples


def compare(baseline, candidate):
    bm, bs, bw = read_run(baseline)
    cm, cs, cw = read_run(candidate)
    team = cm.get("candidate_team")
    if bm.get("support_mode") != "baseline" or cm.get("support_mode") != "possession" or team not in ("RED", "BLUE"):
        raise ValueError("Expected baseline and explicit single-team possession candidate")
    for key in ("seed", "match_test_options", "locomotion_mode", "finishing_aim", "side_transition_mode",
                "source_sha256", "motion_sha256", "fixture_sha256"):
        if bm.get(key) != cm.get(key):
            raise ValueError(f"Uncontrolled comparison: {key} differs")
    if len(bs["actual_modes"]) != 8 or len(cs["actual_modes"]) != 8:
        raise ValueError("Missing player command configuration evidence")
    for name, values in bs["actual_modes"].items():
        if values != ["baseline"]:
            raise ValueError(f"Baseline player {name} did not use baseline")
    for name, values in cs["actual_modes"].items():
        own_team = "RED" if name.startswith("Red") else "BLUE"
        if values != (["possession"] if own_team == team else ["baseline"]):
            raise ValueError(f"Candidate isolation failed for {name}")
    first_difference = None
    for now in sorted(bw.keys() & cw.keys()):
        differences = {n: math.dist(bw[now]["robots"][n]["position"], cw[now]["robots"][n]["position"])
                       for n in bw[now]["robots"]}
        if max(differences.values()) > 1e-8:
            first_difference = {"time": now, "root_position_difference_metres": differences}
            break
    return {"baseline": bs, "candidate": cs, "candidate_team": team,
            "configuration_and_team_isolation_verified": True,
            "first_sampled_root_position_difference": first_difference,
            "limitations": ["One seed and one candidate-side allocation do not establish general performance.",
                "Goals alter subsequent phases and effective playing time.",
                "Tilt episodes, recovery commands and root proximity are different measures, not physical fall counts.",
                "Full ground-truth observations and fixture formations are used."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = compare(args.baseline, args.candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
