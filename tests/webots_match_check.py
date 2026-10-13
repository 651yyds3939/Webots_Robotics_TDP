"""Shortened-clock integration test; durations are explicitly not course defaults."""
import json
import math
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Base.SupervisorBase import SupervisorBase
from Utils.MatchEngine import MatchConfig
from Utils.CourseSpecs import TIME_STEP
from Utils.TeamPolicy import TeamPolicy

options = json.loads(os.environ.get("TDP_MATCH_TEST_OPTIONS", "{}"))
half_seconds = options.get("half_seconds", 60)
ready_seconds = options.get("ready_seconds", 2)
s = SupervisorBase(MatchConfig(half_seconds=half_seconds, startup_seconds=0, ready_seconds=ready_seconds,
                              set_seconds=1, halftime_seconds=1, interruption_seconds=1,
                              preparation_seconds=15 if half_seconds >= 180 else 2,
                              stuck_seconds=options.get("stuck_seconds", 30)))


def place_test_formation():
    """Declared experimental initialization, never counted as player locomotion."""
    positions = {}
    for name, node in s.robots.items():
        team = "RED" if name.startswith("Red") else "BLUE"
        direction = s.match.direction(team)
        point = TeamPolicy(name).home(direction)
        if team == s.match.restart_team and name.endswith("ForwardA"):
            point = (-direction*.3, 0)
        node.getField("translation").setSFVec3f([*point, .334])
        node.getField("rotation").setSFRotation([0, 0, 1, 0 if direction == 1 else math.pi])
        node.resetPhysics()
        node.restartController()
        positions[name] = list(point)
    s.log_file.write(json.dumps({"event": "fixture_formation", "time": s.getTime(),
                                 "half": s.match.half, "positions": positions})+"\n")


try:
    initial = {n: list(node.getPosition()) for n, node in s.robots.items()}
    phases = set()
    max_travel = {n: 0.0 for n in s.robots}
    steps = 0
    playing_seconds = 0
    prepared_halves = set()
    while s.step(TIME_STEP) != -1:
        s.updateMatch()
        if options.get("reset_formation") and s.match.phase == "READY" and s.match.half not in prepared_halves:
            place_test_formation()
            prepared_halves.add(s.match.half)
        s.sendSupervisorData()
        s.updateScoreboard()
        phases.add(s.match.phase)
        if s.match.phase == "PLAYING":
            playing_seconds += TIME_STEP/1000
        for name, node in s.robots.items():
            point = node.getPosition()
            assert all(math.isfinite(c) for c in point), (name, point)
            max_travel[name] = max(max_travel[name], math.dist(initial[name][:2], point[:2]))
        steps += 1
        if steps % 500 == 0:
            print("MATCH_CHECK_PROGRESS", s.getTime(), s.match.phase, flush=True)
        if s.match.phase == "FINISHED":
            assert {"READY", "SET", "PLAYING", "HALFTIME", "FINISHED"} <= phases, phases
            assert max(max_travel.values()) > .15, max_travel
            result = {"simulated_seconds": s.getTime(), "shortened_clock": half_seconds != 600,
                      "test_config": options, "playing_seconds": playing_seconds,
                      "fixture_placement_used": bool(options.get("reset_formation")),
                      "phases": sorted(phases), "score": list(s.score), "max_displacement": max_travel,
                      "behaviour_success_validated": False}
            (s.log_directory / "integration-result.json").write_text(json.dumps(result, indent=2))
            s.exportImage(str(s.log_directory / "match-final.png"), 100)
            print("MATCH_CHECK_OK", json.dumps(result), flush=True)
            s.step(TIME_STEP)
            s.simulationQuit(0)
            break
        if s.getTime() > 2*half_seconds+10:
            raise RuntimeError("Match did not finish within its test-clock limit")
except Exception:
    import traceback
    traceback.print_exc()
    s.step(TIME_STEP)
    s.simulationQuit(1)
