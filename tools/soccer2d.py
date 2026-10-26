"""Small kinematic experiment adapter around the *existing* football policy.

Inspired by the alumni's separation of fast behaviour experiments and 3D
execution. No alumni simulator code or motion assets are copied. This adapter
does not simulate balance, legs, cameras, flight of the ball or physical fouls.
"""
from dataclasses import dataclass, asdict
from collections import Counter
import math
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Wenao/controllers"))
from Utils.CourseSpecs import BALL_RADIUS
from Utils.MatchEngine import MatchConfig, MatchEngine
from Utils.Navigation import Navigator
from Utils.ProcessSupervisor import ROBOT_NAMES
from Utils.TeamPolicy import TeamPolicy, distance


@dataclass(frozen=True)
class Model:
    dt: float = .2
    half_seconds: float = 300
    ready_seconds: float = 10
    # Recorded isolated movement averages, not hardware calibration.
    walk_speed: float = .08525241087733532
    back_speed: float = .034151821846239855
    left_speed: float = .012710006709112306
    right_speed: float = .02229703610271777
    left_turn: float = math.radians(16.873355846361836)/4
    right_turn: float = math.radians(17.348436344702577)/4
    # The following are explicit model assumptions, shared by both teams.
    robot_radius: float = .15
    rolling_deceleration: float = .35
    shot_range: float = .406003256198733
    pass_range: float = .3051396105104535
    shot_seconds: float = 4.8
    pass_seconds: float = 3.299
    kick_noise_radians: float = .04

    def __post_init__(self):
        values = asdict(self)
        if not all(math.isfinite(v) and v > 0 for v in values.values()):
            raise ValueError("Model values must be finite and positive")
        if self.half_seconds <= self.ready_seconds+1:
            raise ValueError("A half must include time after READY/SET")
        if self.dt > .2:
            raise ValueError("Use dt <= 0.2 seconds for contact/boundary sampling")


def wrap(angle):
    return (angle+math.pi) % (2*math.pi)-math.pi


class Simulation:
    def __init__(self, seed=27, candidate_team="RED", candidate="possession", model=None):
        if candidate_team not in ("RED", "BLUE") or candidate not in ("baseline", "possession"):
            raise ValueError("Invalid candidate team or policy")
        self.model = model or Model()
        self.seed, self.candidate_team, self.candidate = seed, candidate_team, candidate
        self.rng = random.Random(seed)
        # One indexed random stream per robot: changes on one team do not consume
        # another player's kick-noise draws. Opponent state can still diverge.
        self.noise = {n: random.Random(f"{seed}:{n}") for n in ROBOT_NAMES}
        self.engine = MatchEngine(MatchConfig(
            half_seconds=self.model.half_seconds, startup_seconds=0,
            ready_seconds=self.model.ready_seconds, set_seconds=1, halftime_seconds=1,
            interruption_seconds=1, preparation_seconds=5, stuck_seconds=120, seed=seed))
        self.time = 0
        self.ball = [0., 0., BALL_RADIUS]
        self.velocity = [0., 0., 0.]
        self.players, self.policies, self.navigators = {}, {}, {}
        for name in ROBOT_NAMES:
            team = "RED" if name.startswith("Red") else "BLUE"
            self.policies[name] = TeamPolicy(name, goal_depth=.30,
                support_mode=candidate if team == candidate_team else "baseline")
            self.navigators[name] = Navigator()
            self.players[name] = {"position": [0., 0., .334], "yaw": 0., "standing": True}
        self.kicking = {}
        self.touch = None
        self.pass_intent = None
        self.pending_pass = None
        self.events = []
        self.stats = {t: Counter() for t in ("RED", "BLUE")}
        self.last_actions = {}
        self.last_decisions = {}
        self.previous_contact = None
        self.prepared = set()
        self._place_formation(jitter=True)

    def _place_formation(self, jitter=False):
        for name, player in self.players.items():
            policy = self.policies[name]
            direction = self.engine.direction(policy.team)
            x, y = policy.home(direction)
            if name.endswith("ForwardA") and policy.team == self.engine.restart_team:
                x, y = -direction*.3, 0
            if jitter:
                x += self.rng.uniform(-.06, .06)
                y += self.rng.uniform(-.06, .06)
            player.update(position=[x, y, .334], yaw=0 if direction == 1 else math.pi)
            self.navigators[name] = Navigator()
        self.kicking.clear()

    def observation(self):
        world = {"version": 2, "time": self.time, "match": self.engine.snapshot(),
                 "ball": {"position": list(self.ball), "velocity": list(self.velocity)},
                 "robots": self.players, "penalties": {}}
        if self.pass_intent and self.pass_intent["expires"] > self.time:
            world["pass_intent"] = self.pass_intent
        return world

    def _event(self, kind, **fields):
        self.events.append({"event": kind, "time": round(self.time, 6), **fields})

    def _contact(self, name):
        self.touch = name
        if name != self.previous_contact:
            self.stats[self.policies[name].team]["contact_transitions"] += 1
            self._event("contact", robot=name)
            self.previous_contact = name
        if self.pending_pass and name != self.pending_pass["sender"]:
            sender = self.pending_pass["sender"]
            completed = name == self.pending_pass["receiver"]
            same_team = self.policies[name].team == self.policies[sender].team
            outcome = "completed_passes" if completed else "misdirected_passes" if same_team else "intercepted_passes"
            self.stats[self.policies[sender].team][outcome] += 1
            self._event("pass_result", sender=sender, receiver=name, completed=completed)
            self.pending_pass = None
            self.pass_intent = None

    def _finish_kick(self, name, decision):
        player = self.players[name]
        dx = self.ball[0]-player["position"][0]
        dy = self.ball[1]-player["position"][1]
        front = dx*math.cos(player["yaw"])+dy*math.sin(player["yaw"])
        lateral = -dx*math.sin(player["yaw"])+dy*math.cos(player["yaw"])
        team = self.policies[name].team
        # A modelled foot contact must still exist at completion; do not kick a
        # ball that an opponent has already moved away during the wind-up.
        if not (.10 <= front <= .30 and abs(lateral-.05) <= .08):
            self.stats[team]["kick_misses"] += 1
            return
        desired_range = self.model.shot_range if decision.kick == "shoot" else self.model.pass_range
        speed = math.sqrt(2*self.model.rolling_deceleration*desired_range)
        angle = player["yaw"]+self.noise[name].gauss(0, self.model.kick_noise_radians)
        self.velocity = [speed*math.cos(angle), speed*math.sin(angle), 0.]
        self._contact(name)
        self.stats[team]["kick_contacts"] += 1
        self._event("kick_contact", robot=name, action=decision.kick)
        if decision.receiver:
            self.pending_pass = {"sender": name, "receiver": decision.receiver, "expires": self.time+24}
            self.pass_intent = {**self.pending_pass, "kind": "pass_intent"}

    def _roll_ball(self):
        """Rolling friction plus first swept contact with a standing body disc."""
        speed = math.hypot(*self.velocity[:2])
        if not speed:
            return
        dt = self.model.dt
        remaining = max(0, speed-self.model.rolling_deceleration*dt)
        travel = (speed+remaining)*.5*min(dt, speed/self.model.rolling_deceleration)
        dx, dy = self.velocity[0]/speed*travel, self.velocity[1]/speed*travel
        squared = dx*dx+dy*dy
        hits = []
        radius = self.model.robot_radius+BALL_RADIUS
        for name, player in self.players.items():
            ox = self.ball[0]-player["position"][0]
            oy = self.ball[1]-player["position"][1]
            # Outgoing foot impulses may start within the body's approximate
            # footprint. They must not reflect off the kicker on the way out.
            if ox*dx+oy*dy >= 0:
                continue
            b = 2*(ox*dx+oy*dy)
            c = ox*ox+oy*oy-radius*radius
            discriminant = b*b-4*squared*c
            if discriminant < 0:
                continue
            fraction = 0 if c < 0 else (-b-math.sqrt(discriminant))/(2*squared)
            if 0 <= fraction <= 1:
                hits.append((fraction, name))
        fraction, name = min(hits) if hits else (1, None)
        self.ball[0] += dx*fraction
        self.ball[1] += dy*fraction
        self.velocity[0] *= remaining/speed
        self.velocity[1] *= remaining/speed
        if name:
            player = self.players[name]
            nx, ny = self.ball[0]-player["position"][0], self.ball[1]-player["position"][1]
            length = max(math.hypot(nx, ny), 1e-9)
            nx, ny = nx/length, ny/length
            inward = self.velocity[0]*nx+self.velocity[1]*ny
            # Assumed inelastic reflection, not calibrated NAO/body contact.
            self.velocity[0] = .35*(self.velocity[0]-2*inward*nx)
            self.velocity[1] = .35*(self.velocity[1]-2*inward*ny)
            self._contact(name)

    def step(self):
        dt = self.model.dt
        self.time += dt
        referee_events = self.engine.step(self.time, self.ball, self.touch)
        for event in referee_events:
            self.events.append(dict(event))
            if event["event"] == "place_ball":
                self.ball = list(event["point"])
                self.velocity = [0., 0., 0.]
                self.touch = self.previous_contact = None
                self.pass_intent = self.pending_pass = None
                self.kicking.clear()
        if self.engine.phase == "READY" and self.engine.half not in self.prepared:
            if self.engine.half == 2:
                self._place_formation(jitter=True)
            self.prepared.add(self.engine.half)
            self._event("fixture_formation", half=self.engine.half)
        if self.pending_pass and self.pending_pass["expires"] <= self.time:
            self.stats[self.policies[self.pending_pass["sender"]].team]["expired_passes"] += 1
            self.pending_pass = self.pass_intent = None
        world = self.observation()
        decisions = {n: p.decide(world) for n, p in self.policies.items()}
        proposed = {}
        actions = {}
        for name, player in self.players.items():
            decision = decisions[name]
            team = self.policies[name].team
            if self.engine.phase == "PLAYING":
                self.stats[team]["playing_player_seconds"] += dt
                direction = self.engine.direction(team)
                if direction*self.ball[0] < -2.5:
                    self.stats[team]["danger_ball_player_seconds"] += dt
                if decision.behaviour == "SUPPORT":
                    self.stats[team]["support_seconds"] += dt
                    behind = direction*player["position"][0] < direction*self.ball[0]
                    if behind:
                        self.stats[team]["support_behind_ball_seconds"] += dt
                    own_distance = min(distance(p["position"], self.ball) for n, p in self.players.items()
                                       if self.policies[n].team == team)
                    other_distance = min(distance(p["position"], self.ball) for n, p in self.players.items()
                                         if self.policies[n].team != team)
                    if other_distance+.20 < own_distance:
                        self.stats[team]["defending_support_seconds"] += dt
                        if behind:
                            self.stats[team]["defending_support_behind_seconds"] += dt
                        if direction*decision.target[0] < direction*self.ball[0]:
                            self.stats[team]["defending_target_behind_seconds"] += dt
            if self.last_decisions.get(name) != decision.behaviour:
                self.stats[team]["decision_transitions"] += 1
                self.last_decisions[name] = decision.behaviour
            if name in self.kicking:
                finish, held = self.kicking[name]
                if self.engine.phase != "PLAYING":
                    del self.kicking[name]
                elif self.time >= finish:
                    self._finish_kick(name, held)
                    del self.kicking[name]
                action = "stand"
            elif decision.behaviour in ("WAIT", "PENALIZED"):
                action = "stand"
            else:
                action, _ = self.navigators[name].choose(decision, player["position"], player["yaw"],
                    self.ball, [p["position"] for n, p in self.players.items() if n != name])
                if action in ("shoot", "pass"):
                    seconds = self.model.shot_seconds if action == "shoot" else self.model.pass_seconds
                    self.kicking[name] = (self.time+seconds, decision)
                    self.stats[team]["shot_attempts" if action == "shoot" else "pass_attempts"] += 1
                    self._event("kick_start", robot=name, action=action, receiver=decision.receiver)
                    if decision.receiver:
                        self.pass_intent = {"kind": "pass_intent", "sender": name,
                                            "receiver": decision.receiver, "expires": self.time+24}
                    action = "stand"
            if action != self.last_actions.get(name):
                self.stats[team]["action_transitions"] += 1
                self.last_actions[name] = action
            if action.startswith(("left", "right")):
                rate = self.model.left_turn if action.startswith("left") else -self.model.right_turn
                player["yaw"] = wrap(player["yaw"]+rate*dt)
            forward = self.model.walk_speed if action == "walk" else -self.model.back_speed if action == "back" else 0
            left = self.model.left_speed if action == "step_left" else -self.model.right_speed if action == "step_right" else 0
            c, s = math.cos(player["yaw"]), math.sin(player["yaw"])
            x, y = player["position"][:2]
            proposed[name] = [max(-4.4, min(4.4, x+(forward*c-left*s)*dt)),
                              max(-2.9, min(2.9, y+(forward*s+left*c)*dt)), .334]
            actions[name] = action
        # Simultaneous, symmetric disc exclusion; no stochastic 'fall success'
        # is invented, and neither player's motion has loop-order priority.
        for _ in range(3):
            offsets = {n: [0., 0.] for n in proposed}
            for i, a in enumerate(ROBOT_NAMES):
                for b in ROBOT_NAMES[i+1:]:
                    sep = distance(proposed[a], proposed[b])
                    overlap = 2*self.model.robot_radius-sep
                    if overlap > 0:
                        if self.engine.phase == "PLAYING" and _ == 0:
                            self.stats[self.policies[a].team]["disc_overlap_player_seconds"] += dt
                            self.stats[self.policies[b].team]["disc_overlap_player_seconds"] += dt
                        ux, uy = ((proposed[a][0]-proposed[b][0])/sep,
                                  (proposed[a][1]-proposed[b][1])/sep) if sep > 1e-9 else (1., 0.)
                        for n, sign in ((a, 1), (b, -1)):
                            offsets[n][0] += sign*ux*overlap*.5
                            offsets[n][1] += sign*uy*overlap*.5
            for n in proposed:
                proposed[n][0] = max(-4.4, min(4.4, proposed[n][0]+offsets[n][0]))
                proposed[n][1] = max(-2.9, min(2.9, proposed[n][1]+offsets[n][1]))
        for name, point in proposed.items():
            self.players[name]["position"] = point
        if self.engine.phase == "PLAYING":
            # Ball pushing is a local contact impulse, not a ball attached to
            # a player or a teleport to the requested destination.
            contacts = []
            for n, p in self.players.items():
                dx, dy = self.ball[0]-p["position"][0], self.ball[1]-p["position"][1]
                front = dx*math.cos(p["yaw"])+dy*math.sin(p["yaw"])
                left = -dx*math.sin(p["yaw"])+dy*math.cos(p["yaw"])
                if .08 < front < .28 and abs(left) < .12 and actions[n] == "walk":
                    contacts.append((distance(p["position"], self.ball), n))
            if contacts and math.hypot(*self.velocity[:2]) < self.model.walk_speed*1.5:
                _, name = min(contacts)
                yaw = self.players[name]["yaw"]
                speed = self.model.walk_speed+self.model.rolling_deceleration*dt*.5
                self.velocity = [speed*math.cos(yaw), speed*math.sin(yaw), 0]
                self._contact(name)
            self._roll_ball()
        else:
            self.velocity = [0., 0., 0.]
        return self.engine.phase != "FINISHED"

    def run(self, trace=None):
        steps = 0
        while self.step():
            steps += 1
            if trace and steps % max(1, round(1/self.model.dt)) == 0:
                import json
                trace.write(json.dumps(self.observation())+"\n")
            if self.time > 2*self.model.half_seconds+5:
                raise RuntimeError("2D match exceeded its configured clock")
        score = self.engine.score
        candidate_index = 0 if self.candidate_team == "RED" else 1
        return {"seed": self.seed, "candidate_team": self.candidate_team,
                "candidate": self.candidate, "score_red_blue": list(score),
                "candidate_goal_difference": score[candidate_index]-score[1-candidate_index],
                "simulated_seconds": self.time, "phase": self.engine.phase,
                "team_stats": {t: dict(v) for t, v in self.stats.items()},
                "model": asdict(self.model), "physics_or_hardware_validated": False,
                "limitations": ["Kinematic discs and contact impulses; no NAO balance or joint dynamics.",
                    "Perfect ground-truth state; no independent camera localisation.",
                    "Ball friction, noise and contact are uncalibrated model assumptions.",
                    "Formation placement at each half is a declared fixture.",
                    "Uses current referee geometry, but not complete physical-foul rules.",
                    "An abstract pass completion is not a validated Webots pass."]}
