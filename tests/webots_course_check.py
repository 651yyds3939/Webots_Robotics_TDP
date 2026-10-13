import sys
import math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from Base.SupervisorBase import SupervisorBase
from Utils.CourseSpecs import TIME_STEP
from Utils.MatchEngine import MatchConfig
s = SupervisorBase(MatchConfig(startup_seconds=0, ready_seconds=0, set_seconds=0))
try:
    pitch = s.getFromDef("PITCH")
    for goal_name in ("POSITIVE_GOAL", "NEGATIVE_GOAL"):
        goal = pitch.getFromProtoDef(goal_name)
        left = goal.getFromProtoDef("LEFT_POST").getField("translation").getSFVec3f()
        right = goal.getFromProtoDef("RIGHT_POST").getField("translation").getSFVec3f()
        bar = goal.getFromProtoDef("CROSSBAR").getField("translation").getSFVec3f()
        assert abs(right[1] - left[1] - .1 - 2.6) < 1e-9
        assert abs(bar[2] - .05 - 1.2) < 1e-9
    print("COURSE_GEOMETRY_OK: clear opening 2.6 x 1.2 m", flush=True)
    taker = s.robots["RedForwardA"]
    taker.getField("translation").setSFVec3f([-.30, 0, .334])
    taker.resetPhysics()
    s.step(TIME_STEP)
    s.place_restart_ball([0, 0, .07])
    point = taker.getField("translation").getSFVec3f()
    assert abs(point[0]+.30) < .02, point
    taker.getField("translation").setSFVec3f([-.10, 0, .334])
    taker.resetPhysics()
    s.step(TIME_STEP)
    s.place_restart_ball([0, 0, .07])
    assert math.dist(taker.getField("translation").getSFVec3f()[:2], [0, 0]) >= .25
    taker.loadState("kickoff")
    taker.resetPhysics()
    print("COURSE_KICKOFF_SEPARATION_OK", flush=True)
    assert s.getBasicTimeStep() == 40
    assert abs(s.ball.getField("translation").getSFVec3f()[2] - .07) < 1e-9
    for name, node in s.robots.items():
        camera = node.getFromProtoDef("HEAD") if False else None
        initial = node.getField("translation").getSFVec3f()
        assert abs(initial[0]) < 4.5 and abs(initial[1]) < 3
    for _ in range(3):
        s.step(TIME_STEP)
        s.updateMatch()
        s.sendSupervisorData()
    # Verify the actual match referee, not a legacy compatibility helper.
    s.match.kickoff_restriction = False
    s.match.released = True
    s.match.previous = [4.49, 1, .07]
    s.setBallPosition([4.51, 1, .07])
    s.step(TIME_STEP)
    s.updateMatch()
    assert s.score == [0, 0], s.score
    s.match.previous = [4.56, 1, .07]
    s.setBallPosition([4.58, 1, .07])
    s.step(TIME_STEP)
    print("SCORER_SAMPLE", s.match.previous, s.ball.getPosition(), flush=True)
    direction = s.match.red_direction
    s.updateMatch()
    assert s.score == ([1, 0] if direction == 1 else [0, 1]), s.score
    s.step(TIME_STEP)
    s.updateMatch()
    s.step(TIME_STEP)
    s.updateMatch()
    assert abs(s.ball.getField("translation").getSFVec3f()[0]) < 1e-3
    # Illegal kickoff positions are removed onto their own side, with no time penalty.
    defender = s.robots["RedDefender"]
    defender.getField("translation").setSFVec3f([s.match.direction("RED"), 0, .334])
    defender.resetPhysics()
    s.match.phase = "READY"
    s.match.phase_started = s.getTime()
    s.step(TIME_STEP)
    s.updateMatch()
    s.step(TIME_STEP)
    p = defender.getPosition()
    assert s.match.direction("RED")*p[0] < 0 and p[1] < -3
    assert "RedDefender" not in s.penalties
    # A restart opponent that fails to retreat is removed for ten seconds.
    s.match.restart_team = "RED"
    s.match.phase = "PREPARE"
    s.match.phase_started = s.getTime()-s.match.config.preparation_seconds
    opponent = s.robots["BlueDefender"]
    opponent.getField("translation").setSFVec3f([.4, 0, .334])
    opponent.resetPhysics()
    s.step(TIME_STEP)
    s.updateMatch()
    assert "BlueDefender" in s.penalties, s.penalties
    print("COURSE_RESTART_ENFORCEMENT_OK", flush=True)
    for i in range(75):
        if s.step(TIME_STEP) == -1:
            raise RuntimeError("Simulation ended early")
        s.updateMatch()
        s.sendSupervisorData()
        s.updateScoreboard()
        if i % 25 == 0:
            print("COURSE_CHECK_STEP", i, flush=True)
        if i == 74:
            s.exportImage("<temporary-project>.png", 100)
    print("COURSE_CHECK_OK: geometry loaded, 8 players, scorer/reset, 3 simulated seconds", flush=True)
    s.step(TIME_STEP)
    s.simulationQuit(0)
except Exception:
    import traceback
    traceback.print_exc()
    s.step(TIME_STEP)
    s.simulationQuit(1)
