"""Checks for experiment validity, not assertions that a policy must win."""
import math
from pathlib import Path
import sys
import subprocess
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from soccer2d import Simulation, Model
from Utils.TeamPolicy import TeamPolicy
from Utils.CourseSpecs import goal_crossing


def defending_world(direction=1):
    simulation = Simulation()
    simulation.engine.phase = "PLAYING"
    simulation.engine.released = True
    simulation.engine.red_direction = direction
    simulation.ball = [-direction*1.5, 0, .07]
    for n, p in simulation.players.items():
        p["position"] = [-direction*4, 2.5, .334] if n.startswith("Red") else [direction*3, 2.5, .334]
    simulation.players["RedForwardA"]["position"] = [-direction*2.5, 1, .334]
    simulation.players["RedDefender"]["position"] = [-direction*2, 0, .334]
    simulation.players["BlueForwardA"]["position"] = [-direction*1.5, .1, .334]
    return simulation.observation()


class SupportExperimentTests(unittest.TestCase):
    def test_only_non_chasing_striker_changes_in_both_directions(self):
        for direction in (-1, 1):
            world = defending_world(direction)
            baseline = TeamPolicy("RedForwardA").decide(world)
            candidate = TeamPolicy("RedForwardA", support_mode="possession").decide(world)
            self.assertEqual(baseline.behaviour, "SUPPORT")
            self.assertEqual(candidate.behaviour, "SUPPORT")
            self.assertLess(direction*candidate.target[0], direction*world["ball"]["position"][0])
            self.assertNotEqual(candidate.target, baseline.target)
            for name in ("RedDefender", "RedGoalkeeper", "BlueForwardA"):
                self.assertEqual(TeamPolicy(name).decide(world),
                                 TeamPolicy(name, support_mode="possession").decide(world))

    def test_own_distance_advantage_preserves_baseline_support(self):
        world = defending_world()
        world["robots"]["RedDefender"]["position"] = [-1.5, .02, .334]
        self.assertEqual(TeamPolicy("RedForwardA").decide(world),
                         TeamPolicy("RedForwardA", support_mode="possession").decide(world))

    def test_same_initial_state_and_opponent_config_when_candidate_swaps(self):
        red = Simulation(27, "RED")
        blue = Simulation(27, "BLUE")
        self.assertEqual(red.observation(), blue.observation())
        for simulation in (red, blue):
            for policy in simulation.policies.values():
                self.assertEqual(policy.support_mode,
                    "possession" if policy.team == simulation.candidate_team else "baseline")

    def test_no_candidate_produces_same_trajectory_when_labels_swap(self):
        model = Model(half_seconds=8, ready_seconds=1)
        red = Simulation(28, "RED", "baseline", model)
        blue = Simulation(28, "BLUE", "baseline", model)
        while red.step():
            self.assertTrue(blue.step())
            self.assertEqual(red.observation(), blue.observation())
        self.assertFalse(blue.step())
        self.assertEqual(red.events, blue.events)

    def test_webots_candidate_requires_explicit_team_and_match(self):
        runner = Path(__file__).with_name("run_webots_check.py")
        for arguments in (("--support-mode", "possession"),
                          ("--match", "--support-mode", "possession", "--output", "unused"),
                          ("--attack", "--support-mode", "possession", "--candidate-team", "RED", "--output", "unused"),
                          ("--candidate-team", "RED")):
            result = subprocess.run([sys.executable, str(runner), *arguments],
                                    capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 2, result.stderr)

    def test_invalid_model_and_policy_rejected(self):
        for kwargs in ({"dt": math.nan}, {"dt": .5}, {"half_seconds": -1}, {"ready_seconds": 500}):
            with self.assertRaises(ValueError):
                Model(**kwargs)
        with self.assertRaises(ValueError):
            TeamPolicy("RedForwardA", support_mode="typo")


class ModelValidityTests(unittest.TestCase):
    def test_repeatability_and_match_completion(self):
        model = Model(half_seconds=8, ready_seconds=1)
        a, b = Simulation(27, model=model), Simulation(27, model=model)
        self.assertEqual(a.run(), b.run())
        self.assertEqual(a.engine.phase, "FINISHED")
        self.assertFalse(a.run()["physics_or_hardware_validated"])

    def test_ball_roll_stops_without_player_or_teleport(self):
        sim = Simulation(model=Model(half_seconds=20, ready_seconds=1))
        sim.engine.phase = "PLAYING"
        sim.engine.half_started = 0
        sim.engine.released = True
        sim.ball = [0, 2.5, .07]
        sim.velocity = [.5, 0, 0]
        for _ in range(12):
            sim.step()
        self.assertAlmostEqual(sim.velocity[0], 0)
        self.assertAlmostEqual(sim.ball[0], .5**2/(2*sim.model.rolling_deceleration), places=6)

    def test_existing_whole_ball_scorer_is_used(self):
        self.assertIsNone(goal_crossing([4.55, 0, .07], [4.56, 0, .07]))
        self.assertEqual(goal_crossing([4.56, 0, .07], [4.58, 0, .07]), "RED")
        sim = Simulation()
        sim.engine.phase = "PLAYING"
        sim.engine.released = True
        sim.engine.kickoff_restriction = False
        sim.engine.previous = [4.56, 0, .07]
        sim.ball = [4.58, 0, .07]
        sim.step()
        self.assertEqual(sim.engine.score, [1, 0])

    def test_kick_can_miss_when_ball_leaves_during_windup(self):
        sim = Simulation()
        sim.ball = [2, 0, .07]
        decision = sim.policies["RedForwardA"].attack([1.8, 0], sim.ball, 1, {}, [])
        before = list(sim.velocity)
        sim._finish_kick("RedForwardA", decision)
        self.assertEqual(sim.velocity, before)
        self.assertEqual(sim.stats["RED"]["kick_misses"], 1)

    def test_standing_goalkeeper_body_blocks_incoming_ball(self):
        sim = Simulation()
        for n, player in sim.players.items():
            player["position"] = [-3, 2, .334]
        sim.players["BlueGoalkeeper"]["position"] = [4.1, 0, .334]
        sim.ball = [3.85, 0, .07]
        sim.velocity = [1, 0, 0]
        sim._roll_ball()
        self.assertLess(sim.ball[0], 4.1)
        self.assertLess(sim.velocity[0], 0)
        self.assertEqual(sim.touch, "BlueGoalkeeper")

    def test_wrong_teammate_touch_is_not_opponent_interception(self):
        sim = Simulation()
        sim.pending_pass = {"sender": "RedForwardA", "receiver": "RedForwardB", "expires": 24}
        sim._contact("RedDefender")
        self.assertEqual(sim.stats["RED"]["misdirected_passes"], 1)
        self.assertEqual(sim.stats["RED"]["intercepted_passes"], 0)


if __name__ == "__main__":
    unittest.main()
