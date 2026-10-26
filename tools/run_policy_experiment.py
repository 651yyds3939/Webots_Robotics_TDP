"""Run paired, team-isolated 2D experiments using current TeamPolicy/Navigator."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

from soccer2d import Model, Simulation, ROOT


def summarize(results):
    outcomes = Counter("win" if r["candidate_goal_difference"] > 0 else
                       "loss" if r["candidate_goal_difference"] < 0 else "draw" for r in results)
    teams = {}
    for label in ("candidate", "baseline"):
        totals = Counter()
        for result in results:
            team = result["candidate_team"]
            if label == "baseline":
                team = "BLUE" if team == "RED" else "RED"
            totals.update(result["team_stats"][team])
        denominator = totals.get("support_seconds", 0)
        defensive_time = totals.get("defending_support_seconds", 0)
        teams[label] = {**dict(totals), "support_behind_fraction":
                       totals.get("support_behind_ball_seconds", 0)/denominator if denominator else None,
                       "defending_support_behind_fraction":
                       totals.get("defending_support_behind_seconds", 0)/defensive_time if defensive_time else None,
                       "danger_ball_fraction": totals.get("danger_ball_player_seconds", 0)/
                       max(totals.get("playing_player_seconds", 0), 1)}
    differences = [r["candidate_goal_difference"] for r in results]
    return {"games": len(results), "outcomes": dict(outcomes),
            "mean_candidate_goal_difference": statistics.mean(differences) if differences else None,
            "team_totals": teams,
            "interpretation": "Model-only exploratory comparison; no 3D or hardware performance claim.",
            "statistical_significance_validated": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=[27, 28, 29])
    parser.add_argument("--candidate", choices=("baseline", "possession"), default="possession")
    parser.add_argument("--half-seconds", type=float, default=300)
    parser.add_argument("--ready-seconds", type=float, default=10)
    parser.add_argument("--dt", type=float, default=.2)
    parser.add_argument("--rolling-deceleration", type=float, default=.35,
                        help="Shared, uncalibrated ball-model assumption; use for sensitivity checks")
    parser.add_argument("--trace", action="store_true", help="Save full observations at 1 Hz")
    parser.add_argument("--output", required=True, type=Path, help="Fresh output directory")
    args = parser.parse_args(argv)
    if len(set(args.seeds)) != len(args.seeds):
        parser.error("Use distinct seeds; duplicate seeds are not independent replicates")
    try:
        model = Model(dt=args.dt, half_seconds=args.half_seconds, ready_seconds=args.ready_seconds,
                      rolling_deceleration=args.rolling_deceleration)
    except ValueError as exc:
        parser.error(str(exc))
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("Use a fresh output directory")
    args.output.mkdir(parents=True, exist_ok=True)
    sources = [Path(__file__), Path(__file__).with_name("soccer2d.py")]
    sources += [ROOT / "Wenao/controllers/Utils" / (name+".py") for name in
                ("TeamPolicy", "Navigation", "MatchEngine", "CourseSpecs")]
    manifest = {"mode": "kinematic_2d_policy_comparison", "python": sys.version,
                "candidate": args.candidate, "baseline": "baseline", "seeds": args.seeds,
                "candidate_teams": ["RED", "BLUE"], "paired_layouts": True,
                "formation_fixture": True, "default_webots_policy_changed": False,
                "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    for source in sources:
        snapshot = args.output / "source_snapshot" / source.relative_to(ROOT)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(source.read_bytes())
    try:
        manifest["git_head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        manifest["git_head"] = None
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    results = []
    started = time.monotonic()
    for seed in args.seeds:
        for team in ("RED", "BLUE"):
            run_dir = args.output / f"seed-{seed}-{team.lower()}"
            run_dir.mkdir()
            simulation = Simulation(seed, team, args.candidate, model)
            if args.trace:
                with (run_dir / "observations.jsonl").open("w") as trace:
                    result = simulation.run(trace)
            else:
                result = simulation.run()
            (run_dir / "result.json").write_text(json.dumps(result, indent=2)+"\n")
            with (run_dir / "events.jsonl").open("w") as events:
                for event in simulation.events:
                    events.write(json.dumps(event)+"\n")
            results.append(result)
            print(f"2D_RESULT seed={seed} candidate={team} score={result['score_red_blue']} "
                  f"goal_difference={result['candidate_goal_difference']}", flush=True)
    summary = summarize(results)
    summary["wall_seconds"] = time.monotonic()-started
    summary["candidate"] = args.candidate
    summary["seeds"] = args.seeds
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2)+"\n")
    print("2D_EXPERIMENT_COMPLETE", json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
