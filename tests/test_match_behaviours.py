import copy
import json
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Wenao/controllers"))
from Utils.MatchEngine import MatchConfig, MatchEngine, boundary_crossing
from Utils.TeamPolicy import TeamPolicy, lane_clear
from Utils.ProcessSupervisor import SupervisorData, ROBOT_NAMES
from Utils.VisionGeometry import ball_world_position


def playing():
    engine = MatchEngine(MatchConfig(startup_seconds=0, ready_seconds=0, set_seconds=0))
    engine.red_direction = 1
    for now in (0, .04, .08):
        engine.step(now, [0, 0, .07])
    engine.released = True
    engine.kickoff_restriction = False
    return engine


def world():
    match = playing().snapshot()
    robots = {}
    for name in ROBOT_NAMES:
        policy = TeamPolicy(name)
        direction = 1 if name.startswith("Red") else -1
        robots[name] = {"position": [*policy.home(direction), .334], "yaw": 0 if direction == 1 else math.pi}
    return {"version": 2, "time": 1, "match": match, "ball": {"position": [0, 0, .07], "velocity": [0, 0, 0]},
            "robots": robots, "penalties": {}}


class RefereeTests(unittest.TestCase):
    def test_clock_half_swap_and_finish_including_stoppages(self):
        engine = MatchEngine(MatchConfig(half_seconds=10, startup_seconds=1, ready_seconds=2, set_seconds=1, halftime_seconds=1))
        first_direction, kickoff = engine.red_direction, engine.initial_kickoff
        for t, phase in ((0, "INITIAL"), (1, "READY"), (3, "SET"), (4, "PLAYING"), (11, "HALFTIME"), (12, "READY"), (22, "FINISHED")):
            engine.step(t, [0, 0, .07])
            self.assertEqual(engine.phase, phase)
        self.assertEqual(engine.red_direction, -first_direction)
        self.assertNotEqual(engine.restart_team, kickoff)

    def test_partial_crossing_not_out_and_first_diagonal_boundary(self):
        self.assertIsNone(boundary_crossing([0, 2.99, .07], [0, 3.01, .07]))
        crossing = boundary_crossing([4.5, 3, .07], [4.6, 3.3, .07])
        self.assertEqual(crossing[1], 1)

    def test_throw_in_awarded_to_other_team_at_crossing(self):
        engine = playing()
        engine.previous = [1, 3.06, .07]
        engine.step(1, [2, 3.08, .07], "RedForwardA")
        self.assertEqual((engine.restart, engine.restart_team), ("THROW_IN", "BLUE"))
        self.assertAlmostEqual(engine.restart_point[0], 1.5)
        self.assertEqual(engine.restart_point[1], 3)

    def test_hl_goal_kick_and_corner_placement(self):
        for touch, kind, team, point in (("RedForwardA", "GOAL_KICK", "BLUE", [0, 3, .07]),
                                          ("BlueDefender", "CORNER", "RED", [4.5, 3, .07])):
            engine = playing()
            engine.previous = [4.56, 2, .07]
            engine.step(1, [4.58, 2, .07], touch)
            self.assertEqual((engine.restart, engine.restart_team, engine.restart_point), (kind, team, point))

    def test_scoring_changes_with_ends_and_conceding_kickoff(self):
        for direction, scoring in ((1, "RED"), (-1, "BLUE")):
            engine = playing()
            engine.red_direction = direction
            engine.previous = [4.56, 0, .07]
            engine.step(1, [4.58, 0, .07])
            self.assertEqual(engine.score, [1, 0] if scoring == "RED" else [0, 1])
            self.assertNotEqual(engine.restart_team, scoring)

    def test_indirect_restart_cannot_score_without_second_player_touch(self):
        engine = playing()
        engine.indirect, engine.restart_team = True, "RED"
        engine.previous = [4.56, 0, .07]
        engine.step(1, [4.58, 0, .07], "RedForwardA")
        self.assertEqual(engine.score, [0, 0])
        self.assertEqual(engine.restart, "GOAL_KICK")
        engine = playing()
        engine.indirect, engine.restart_team = True, "RED"
        engine.step(.2, [1, 0, .07], "RedForwardA")
        engine.step(.3, [2, 0, .07], "RedForwardB")
        engine.previous = [4.56, 0, .07]
        engine.step(1, [4.58, 0, .07])
        self.assertEqual(engine.score, [1, 0])

    def test_unknown_touch_is_not_invented(self):
        engine = playing()
        engine.previous = [1, 3.06, .07]
        engine.step(1, [1, 3.08, .07])
        self.assertEqual(engine.restart, "DROP_BALL")

    def test_stuck_ball_and_invalid_clock(self):
        engine = playing()
        engine.step(121, [0, 0, .07])
        self.assertEqual(engine.restart, "DROP_BALL")
        with self.assertRaises(ValueError):
            engine.step(120, [0, 0, .07])
        with self.assertRaises(ValueError):
            MatchConfig(half_seconds=0)


class RoleTests(unittest.TestCase):
    def test_one_chaser_per_team_and_support(self):
        w = world()
        decisions = {n: TeamPolicy(n).decide(w) for n in ROBOT_NAMES}
        for prefix in ("Red", "Blue"):
            self.assertEqual(sum(d.behaviour == "INTERCEPT" for n, d in decisions.items() if n.startswith(prefix)), 1)
        self.assertEqual(decisions["RedGoalkeeper"].behaviour, "GUARD")

    def test_pass_when_shot_lane_blocked(self):
        w = world()
        w["ball"]["position"] = [2, 0, .07]
        w["robots"]["RedForwardA"]["position"] = [1.8, 0, .334]
        w["robots"]["RedForwardB"]["position"] = [3, 1, .334]
        w["robots"]["BlueDefender"]["position"] = [3, 0, .334]
        w["robots"]["BlueForwardA"]["position"] = [-1, -2, .334]
        w["robots"]["BlueForwardB"]["position"] = [-1, 2, .334]
        decision = TeamPolicy("RedForwardA").decide(w)
        self.assertEqual((decision.behaviour, decision.kick, decision.receiver), ("PASS", "pass", "RedForwardB"))

    def test_shoot_and_dribble_are_distinct(self):
        w = world()
        for n in w["robots"]:
            if n.startswith("Blue"):
                w["robots"][n]["position"] = [-3, 2, .334]
        for x, behaviour, kick in ((4.2, "SHOOT", "shoot"), (0, "DRIBBLE", ""), (2, "DRIBBLE", "")):
            w["ball"]["position"] = [x, 0, .07]
            w["robots"]["RedForwardA"]["position"] = [x-.19, 0, .334]
            decision = TeamPolicy("RedForwardA").decide(w)
            self.assertEqual((decision.behaviour, decision.kick), (behaviour, kick))

    def test_goalkeeper_predicts_crossing(self):
        w = world()
        w["ball"] = {"position": [-2, .4, .07], "velocity": [-1, .2, 0]}
        decision = TeamPolicy("RedGoalkeeper").decide(w)
        self.assertEqual(decision.behaviour, "GUARD_INTERCEPT")
        self.assertAlmostEqual(decision.target[1], .824)

    def test_pass_receiver_approaches_ball_and_sender_yields(self):
        w = world()
        w["pass_intent"] = {"sender": "RedForwardA", "receiver": "RedForwardB", "expires": 25}
        self.assertEqual(TeamPolicy("RedForwardB").decide(w).behaviour, "RECEIVE_PASS")
        self.assertEqual(TeamPolicy("RedForwardA").decide(w).behaviour, "SUPPORT_PASS")

    def test_match_stop_penalty_and_restart_exclusion(self):
        w = world()
        w["match"]["phase"] = "FINISHED"
        self.assertEqual(TeamPolicy("RedForwardA").decide(w).behaviour, "WAIT")
        w["penalties"]["RedForwardA"] = 10
        self.assertEqual(TeamPolicy("RedForwardA").decide(w).behaviour, "PENALIZED")
        w = world()
        w["match"].update(phase="PREPARE", restart_team="BLUE", released=False)
        w["robots"]["RedForwardA"]["position"] = [.1, 0, .334]
        decision = TeamPolicy("RedForwardA").decide(w)
        self.assertEqual(decision.behaviour, "KEEP_DISTANCE")
        self.assertGreaterEqual(math.hypot(*decision.target), .75)


class PacketTests(unittest.TestCase):
    class Receiver:
        def __init__(self, packet):
            self.packet = packet
        def getString(self):
            return self.packet
        def nextPacket(self):
            pass

    def test_zero_is_numeric_and_bad_packet_preserves_last_observation(self):
        reader = SupervisorData("RedForwardA")
        reader.updateData(self.Receiver("2,0"))
        self.assertFalse(reader.data["GameStatus"])
        good = world()
        self.assertTrue(reader.updateData(self.Receiver(json.dumps(good))))
        bad = copy.deepcopy(good)
        bad["ball"]["position"][0] = float("nan")
        self.assertFalse(reader.updateData(self.Receiver(json.dumps(bad))))
        self.assertEqual(reader.world, good)
        self.assertFalse(reader.updateData(self.Receiver('{"version":2}')))

    def test_projection_uses_capture_pose_not_latest_pose(self):
        detection = {"capture": {"time": 1, "pose": {"position": [1, 2, .334], "yaw": math.pi/2},
                                  "head_yaw": 0, "head_pitch": -.692901},
                     "depth": 2, "bearing": 0, "elevation_down": 0}
        estimate = ball_world_position(detection)
        self.assertAlmostEqual(estimate[0], 1)
        self.assertAlmostEqual(estimate[1], 4.05071)


if __name__ == "__main__":
    unittest.main()
