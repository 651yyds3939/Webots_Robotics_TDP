"""Physical execution experiments, not a claimed skill success rate."""
import json
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Base.SupervisorBase import SupervisorBase
from Utils.MatchEngine import MatchConfig
from Utils.CourseSpecs import TIME_STEP, goal_crossing

s = SupervisorBase(MatchConfig(half_seconds=600, startup_seconds=0, ready_seconds=1,
                              set_seconds=1, stuck_seconds=120))
try:
    results = []
    for skill, ball, own, receiver in (("shoot", [4.2, 0, .07], [4.03, -.05, .334], [0, 2, .334]),
                                       ("dribble", [0, 0, .07], [-.19, 0, .334], [-1, 2, .334]),
                                       ("pass", [2, 0, .07], [2-.12/math.sqrt(2), -.22/math.sqrt(2), .334], [2.55, .55, .334])):
        # Test fixture placement only. Player controller receives no teleport interface.
        s.match.phase = "SET"
        s.match.phase_started = s.getTime()
        for i, (name, node) in enumerate(s.robots.items()):
            point = [-3+(i-4)*.7, (-2.3 if i%2 else 2.3), .334] if name.startswith("Blue") else [-4+i*.7, 2, .334]
            if name == "RedForwardA":
                point = own
            elif name == "RedForwardB":
                point = receiver
            elif name == "BlueDefender" and skill == "pass":
                point = [3, 0, .334]
            node.getField("translation").setSFVec3f(point)
            angle = math.pi/4 if name == "RedForwardA" and skill == "pass" else math.atan2(ball[1]-point[1], ball[0]-point[0]) if name == "RedForwardB" and skill == "pass" else 0
            node.getField("rotation").setSFRotation([0, 0, 1, angle])
            node.resetPhysics()
            node.restartController()
        s.setBallPosition(ball)
        for _ in range(40):
            s.step(TIME_STEP)
            s.sendSupervisorData()
        s.match.phase = "PLAYING"
        s.match.red_direction = 1
        s.match.released = True
        s.match.kickoff_restriction = False
        s.match.indirect = False
        s.match.restart_touch = s.match.last_touch = None
        s.match.previous = list(s.ball.getPosition())
        start = list(s.ball.getPosition())
        maximum = 0
        touches = set()
        previous = start
        scored = False
        for _ in range(600 if skill == "pass" else 300):
            if s.step(TIME_STEP) == -1:
                raise RuntimeError("Simulation stopped")
            s.sendSupervisorData()
            touch = s.physical_touch()
            if touch:
                touches.add(touch)
                s.match.last_touch = touch
            current = list(s.ball.getPosition())
            scored = scored or goal_crossing(previous, current) is not None
            previous = current
            maximum = max(maximum, math.dist(current[:2], start[:2]))
        result = {"fixture": skill, "start_ball": start, "end_ball": current,
                  "max_ball_displacement": maximum, "physical_contacts": sorted(touches),
                  "goal_crossed": scored, "receiver_contact": "RedForwardB" in touches,
                  "success_rate_validated": False}
        results.append(result)
        print("SKILL_MEASUREMENT", json.dumps(result), flush=True)
    (s.log_directory / "skills-result.json").write_text(json.dumps(results, indent=2))
    # Independent gates prevent a working dribble from hiding a failed pass or shot.
    assert results[0]["goal_crossed"], results[0]
    assert results[1]["max_ball_displacement"] > .10 and "RedForwardA" in results[1]["physical_contacts"], results[1]
    assert results[2]["receiver_contact"], results[2]
    print("SKILL_CHECK_OK: close-range goal, physical dribble, receiver contact; fixture outcomes only", flush=True)
    s.step(TIME_STEP)
    s.simulationQuit(0)
except Exception:
    import traceback
    traceback.print_exc()
    s.simulationQuit(1)
