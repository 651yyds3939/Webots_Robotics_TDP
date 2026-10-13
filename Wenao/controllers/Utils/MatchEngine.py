"""Deterministic match clock and restart decisions, independent of Webots.

Rules: course-linked RC-HL-2025, Laws 7--10 and 15--17. A referee adapter
supplies physical contacts; this module never mistakes proximity for a touch.
Physical fouls and tournament administration need separate adjudication.
"""
from dataclasses import dataclass
import math
import random
from Utils.CourseSpecs import BALL_RADIUS, goal_crossing


def opposite(team):
    return "BLUE" if team == "RED" else "RED"


def boundary_crossing(previous, current):
    """First whole-ball exit, including airborne and diagonal crossings."""
    candidates = []
    for axis, limit in ((0, 4.5 + BALL_RADIUS), (1, 3 + BALL_RADIUS)):
        for sign in (-1, 1):
            before, after = sign * previous[axis], sign * current[axis]
            if before <= limit < after:
                t = (limit - before) / (after - before)
                point = [a + t * (b-a) for a, b in zip(previous, current)]
                candidates.append((t, axis, sign, point))
    return min(candidates, default=None)


@dataclass(frozen=True)
class MatchConfig:
    half_seconds: float = 600.0
    startup_seconds: float = 120.0
    ready_seconds: float = 45.0
    set_seconds: float = 5.0
    halftime_seconds: float = 15.0
    interruption_seconds: float = 5.0
    preparation_seconds: float = 15.0
    release_seconds: float = 10.0
    stuck_seconds: float = 120.0
    seed: int = 27

    def __post_init__(self):
        durations = [v for k, v in self.__dict__.items() if k != "seed"]
        if not all(math.isfinite(v) and v >= 0 for v in durations):
            raise ValueError("Match durations must be finite and non-negative")
        if self.half_seconds <= 0:
            raise ValueError("A half must have positive duration")


class MatchEngine:
    def __init__(self, config=MatchConfig()):
        self.config = config
        rng = random.Random(config.seed)
        self.red_direction = rng.choice((-1, 1))
        self.initial_kickoff = rng.choice(("RED", "BLUE"))
        self.half = 1
        self.score = [0, 0]
        self.phase = "INITIAL"
        self.phase_started = 0.0
        self.half_started = None
        self.last_time = 0.0
        self.restart = "KICKOFF"
        self.restart_team = self.initial_kickoff
        self.restart_point = [0.0, 0.0, BALL_RADIUS]
        self.restart_touch = None
        self.indirect = False
        self.kickoff_restriction = True
        self.released = False
        self.last_touch = None
        self.previous = None
        self.stuck_anchor = [0.0, 0.0]
        self.stuck_since = 0.0
        self.events = []

    def direction(self, team):
        return self.red_direction if team == "RED" else -self.red_direction

    def transition(self, phase, now):
        self.phase, self.phase_started = phase, now
        self.events.append({"event": "phase", "phase": phase, "time": now})

    def begin_restart(self, kind, team, point, now):
        self.restart, self.restart_team = kind, team
        self.restart_point = list(point)
        self.restart_touch = None
        self.last_touch = None
        self.indirect = kind in ("THROW_IN", "INDIRECT_FREE_KICK")
        self.kickoff_restriction = kind == "KICKOFF"
        self.released = kind == "DROP_BALL"
        self.previous = None
        self.stuck_anchor, self.stuck_since = list(point[:2]), now
        self.transition("READY" if kind in ("KICKOFF", "DROP_BALL") else "STOPPED", now)
        self.events.append({"event": "restart", "kind": kind, "team": team,
                            "point": list(point), "time": now})

    def goal_restart(self, end, y, last_team, now):
        defending = "RED" if self.direction("RED") == -end else "BLUE"
        side = 1 if y >= 0 else -1
        if last_team == defending:
            self.begin_restart("CORNER", opposite(defending), [end*4.5, side*3, BALL_RADIUS], now)
        else:
            # HL 2025 Law 16: midfield/touch-line intersection, not goal area.
            self.begin_restart("GOAL_KICK", defending, [0, side*3, BALL_RADIUS], now)

    def step(self, now, ball, touch=None):
        if not math.isfinite(now) or now < self.last_time:
            raise ValueError("Match time must advance monotonically")
        self.last_time = now
        self.events = []
        if self.phase == "FINISHED":
            return self.events
        if self.half_started is not None and now-self.half_started >= self.config.half_seconds:
            if self.half == 1:
                self.half = 2
                self.red_direction *= -1
                self.half_started = None
                self.restart_team = opposite(self.initial_kickoff)
                self.transition("HALFTIME", now)
            else:
                self.transition("FINISHED", now)
            return self.events
        elapsed = now-self.phase_started
        if self.phase == "INITIAL" and elapsed >= self.config.startup_seconds:
            self.half_started = now
            self.begin_restart("KICKOFF", self.initial_kickoff, [0, 0, BALL_RADIUS], now)
        elif self.phase == "HALFTIME" and elapsed >= self.config.halftime_seconds:
            self.half_started = now
            self.begin_restart("KICKOFF", opposite(self.initial_kickoff), [0, 0, BALL_RADIUS], now)
        elif self.phase == "READY" and elapsed >= self.config.ready_seconds:
            self.transition("SET", now)
            self.events.append({"event": "place_ball", "point": self.restart_point, "time": now})
        elif self.phase == "SET" and elapsed >= self.config.set_seconds:
            self.transition("PLAYING", now)
            self.stuck_since = now
        elif self.phase == "STOPPED" and elapsed >= self.config.interruption_seconds:
            self.transition("PREPARE", now)
            self.events.append({"event": "place_ball", "point": self.restart_point, "time": now})
        elif self.phase == "PREPARE" and elapsed >= self.config.preparation_seconds:
            self.transition("PLAYING", now)
            self.stuck_since = now
        if self.phase != "PLAYING":
            self.previous = list(ball)
            return self.events

        if touch and touch != self.last_touch:
            self.last_touch = touch
            if self.restart_touch is None:
                self.restart_touch = touch
            elif touch != self.restart_touch:
                self.indirect = self.kickoff_restriction = False
        if math.dist(ball[:2], self.restart_point[:2]) >= .05 or now-self.phase_started >= self.config.release_seconds:
            self.released = True
        if math.hypot(*ball[:2]) > .75+BALL_RADIUS:
            self.kickoff_restriction = False
        if self.previous is not None:
            crossing = boundary_crossing(self.previous, ball)
            if crossing:
                _, axis, end, point = crossing
                geometric = goal_crossing(self.previous, ball) if axis == 0 else None
                last_team = ("RED" if self.last_touch.startswith("Red") else "BLUE") if self.last_touch else None
                if geometric:
                    scoring = "RED" if self.direction("RED") == end else "BLUE"
                    disallowed = self.indirect or (self.kickoff_restriction and scoring == self.restart_team)
                    own_restart_goal = (self.restart_touch and scoring != self.restart_team
                                        and self.last_touch == self.restart_touch)
                    if disallowed or own_restart_goal:
                        # Direct restart into own goal -> corner; indirect into opponents' -> goal kick.
                        last_team = self.restart_team
                        self.goal_restart(end, point[1], last_team, now)
                    else:
                        self.score[0 if scoring == "RED" else 1] += 1
                        self.events.append({"event": "goal", "team": scoring, "time": now})
                        self.begin_restart("KICKOFF", opposite(scoring), [0, 0, BALL_RADIUS], now)
                elif axis == 1:
                    if last_team is None:
                        self.begin_restart("DROP_BALL", None, [0, 0, BALL_RADIUS], now)
                    else:
                        self.begin_restart("THROW_IN", opposite(last_team),
                                           [max(-4.5, min(4.5, point[0])), end*3, BALL_RADIUS], now)
                else:
                    if last_team is None:
                        self.begin_restart("DROP_BALL", None, [0, 0, BALL_RADIUS], now)
                    else:
                        self.goal_restart(end, point[1], last_team, now)
                return self.events
        if math.dist(ball[:2], self.stuck_anchor) >= .05:
            self.stuck_anchor, self.stuck_since = list(ball[:2]), now
        elif now-self.stuck_since >= self.config.stuck_seconds:
            self.begin_restart("DROP_BALL", None, [0, 0, BALL_RADIUS], now)
        self.previous = list(ball)
        return self.events

    def snapshot(self):
        remaining = self.config.half_seconds if self.half_started is None else max(
            0, self.config.half_seconds-(self.last_time-self.half_started))
        return {"phase": self.phase, "half": self.half, "remaining": remaining,
                "score": list(self.score), "red_direction": self.red_direction,
                "restart": self.restart, "restart_team": self.restart_team,
                "restart_point": list(self.restart_point), "released": self.released,
                "last_touch": self.last_touch}
