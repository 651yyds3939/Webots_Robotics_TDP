"""
The Basic Supervisor class.
All Supervisor classes should be derived from this class.
"""

import os
import sys
import json
import math
import configparser
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import replace
import numpy as np

from controller import Supervisor
from Utils import Functions
from Utils.CourseSpecs import BALL_RADIUS, PITCH_LENGTH, PITCH_WIDTH, goal_crossing
from Utils.MatchEngine import MatchEngine, MatchConfig

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))


class SupervisorBase(Supervisor):
    RobotList = [
        "RedGoalkeeper",
        "RedDefender",
        "RedForwardB",
        "RedForwardA",
        "BlueGoalkeeper",
        "BlueDefender",
        "BlueForwardB",
        "BlueForwardA",
    ]

    def __init__(self, match_config=None):
        super().__init__()

        self.emitter = self.getDevice("emitter")
        self.ball = self.getFromDef("BALL")
        self.robots = {name: self.getFromDef(name) for name in self.RobotList}
        self.latestGoalTime = 0
        self.previousBallLocation = [0, 0, BALL_RADIUS]
        self.previousGoalSample = self.ball.getPosition()
        self.ball.saveState("kickoff")
        for robot in self.robots.values():
            robot.saveState("kickoff")
        settings = configparser.ConfigParser()
        settings.read(Path(__file__).resolve().parents[1] / "Utils/globalconfig.ini")
        values = {key: settings.getfloat("Match", key) for key in MatchConfig.__dataclass_fields__ if key != "seed"}
        values["seed"] = int(os.environ.get("TDP_MATCH_SEED", settings.getint("Match", "seed")))
        configuration = match_config or MatchConfig(**values)
        if "TDP_MATCH_SEED" in os.environ:
            configuration = replace(configuration, seed=int(os.environ["TDP_MATCH_SEED"]))
        self.match = MatchEngine(configuration)
        if self.match.red_direction == -1:
            # Random side assignment is an initial referee placement, before play.
            for name, robot in self.robots.items():
                position = robot.getField("translation").getSFVec3f()
                robot.getField("translation").setSFVec3f([-position[0], -position[1], position[2]])
                robot.getField("rotation").setSFRotation([0, 0, 1, math.pi if name.startswith("Red") else 0])
                robot.resetPhysics()
                robot.saveState("kickoff")
        self.score = self.match.score
        self.penalties = {}
        self.fallen_since = {}
        self.outside_since = {}
        self.last_log_time = -1
        self.log_directory = Path(os.environ.get("TDP_RUN_DIR", str(Path(__file__).resolve().parents[3] / "runs")))
        self.log_directory.mkdir(parents=True, exist_ok=True)
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + f"-{os.getpid()}"
        self.log_file = (self.log_directory / f"match-{self.run_id}.jsonl").open("w", buffering=1)
        self.log_file.write(json.dumps({"event": "configuration", "config": self.match.config.__dict__,
                                       "observation_source": "supervisor", "model_validated_on_hardware": False})+"\n")
        Red = "Red"
        Blue = "Blue"
        self.setLabel(0, "█" * 100, 0, 0, 0.1, 0xFFFFFF, 0.3, "Lucida Console")
        self.setLabel(1, "█" * 100, 0, 0.048, 0.1, 0xFFFFFF, 0.3, "Lucida Console")
        self.setLabel(2, Red, 0.01, 0.003, 0.08, 0xFF0000, 0, "Arial")
        self.setLabel(3, Blue, 0.01, 0.051, 0.08, 0x0000FF, 0, "Arial")

    def updateScoreboard(self):
        for i in range(2):
            color = 0xFF0000 if i == 0 else 0x0000FF
            self.setLabel(
                4 + i,
                "{:d}".format(self.score[i]),
                0.8,
                0.003 + 0.048 * i,
                0.08,
                color,
                0,
                "Arial",
            )

    def isitGoal(self):
        ball_coordinate = self.getBallPosition()
        goal_team = goal_crossing(self.previousGoalSample, ball_coordinate)
        self.previousGoalSample = list(ball_coordinate)
        if goal_team is not None:
            print(f"{goal_team} GOAL!")
            self.score[0 if goal_team == "RED" else 1] += 1
            self.resetSimulation()

    def getBallPosition(self) -> list:
        """Get the soccer ball coordinate on the field.

        Returns:
            list: x, y, z coordinates.
        """
        newBallLocation = self.ball.getPosition()

        if (abs(newBallLocation[0]) < PITCH_LENGTH / 2
                and abs(newBallLocation[1]) < PITCH_WIDTH / 2):
            if (
                max(
                    abs(a - b)
                    for a, b in zip(self.previousBallLocation, newBallLocation)
                )
                > 0.05
            ):
                self.previousBallLocation = newBallLocation

        return newBallLocation

    def setBallPosition(self, ballPosition) -> None:
        """Set the soccer ball coordinate on the field.

        Args:
            list: x, y, z coordinates.
        """
        self.previousBallLocation = ballPosition
        self.ball.getField("translation").setSFVec3f(ballPosition)
        self.ball.resetPhysics()

    def getRobotPosition(self, robotName) -> list:
        """Get the robot coordinate on the field.

        Returns:
            list: x, y, z coordinates.
        """
        return self.robots[robotName].getPosition()

    def getRobotAngle(self, robotName):
        """Get the robot angle on the field.

        Args:
            robotName (str): The name of the robot.

        Returns:
            float: The robot angle in radians.
        """
        orientation = self.robots[robotName].getOrientation()
        angle = np.arctan2(orientation[3], orientation[0])
        return angle

    def getBallOwner(self) -> str:
        """Calculate the ball owner team from the distances from the ball and the orientation of the robots.

        Returns:
            str: Ball owner team first letter.
        """
        ballPosition = self.getBallPosition()
        scores = {}
        for name in self.robots:
            robotPosition = self.getRobotPosition(name)
            robotAngle = self.getRobotAngle(name)
            ballAngle = np.arctan2(
                ballPosition[1] - robotPosition[1], ballPosition[0] - robotPosition[0]
            )
            angleDiff = abs((ballAngle - robotAngle + np.pi) % (2 * np.pi) - np.pi)
            distance = Functions.calculateDistance(ballPosition, robotPosition)
            # Lower scores are better. A small distance and a small angle difference result in a small score.
            # Square the distance to give more weight to the distance.
            scores[name] = distance**2 + angleDiff

        ballOwnerRobotName = min(scores, key=scores.get)

        return ballOwnerRobotName.ljust(9, "*")

    def sendSupervisorData(self) -> None:
        """Broadcast one complete referee observation; players cannot set its phase."""
        world = self.observation()
        self.emitter.send(json.dumps(world, allow_nan=False).encode("utf-8"))
        if self.getTime()-self.last_log_time >= .2 or self.match.phase == "FINISHED":
            self.log_file.write(json.dumps({"event": "sample", **world})+"\n")
            self.last_log_time = self.getTime()

    def observation(self):
        return {"version": 2, "time": self.getTime(), "match": self.match.snapshot(),
                "ball": {"position": list(self.getBallPosition()), "velocity": list(self.ball.getVelocity()[:3])},
                "ball_owner": self.getBallOwner().strip("*"),
                "robots": {name: {"position": list(node.getPosition()), "yaw": float(self.getRobotAngle(name)),
                                  "standing": node.getOrientation()[8] >= .5}
                           for name, node in self.robots.items()},
                "penalties": dict(self.penalties)}

    def physical_touch(self):
        """Resolve ball-surface contacts; exclude turf-only contacts near its bottom.

        Webots exposes contact locations rather than an unambiguous opponent ID.
        Simultaneous contacts are resolved by surface error then robot name and
        logged, so the approximation is visible during referee validation.
        """
        ball = self.ball.getPosition()
        candidates = []
        for name, node in self.robots.items():
            if name in self.penalties:
                continue
            for contact in node.getContactPoints(True):
                point = contact.point
                error = abs(math.dist(point, ball)-BALL_RADIUS)
                if error < .012 and point[2] > ball[2]-BALL_RADIUS+.006:
                    candidates.append((error, name))
        return min(candidates)[1] if candidates else None

    def place_restart_ball(self, point):
        self.setBallPosition(point)
        # Separation is a referee placement, never a player locomotion shortcut.
        for name, node in self.robots.items():
            position = node.getPosition()
            # Only separate near-overlapping placements. A legal kickoff taker
            # 0.30 m behind the ball must not be displaced as though colliding.
            # Opponent exclusion distance is adjudicated separately below.
            if math.dist(position[:2], point[:2]) < .25:
                direction = self.match.direction("RED" if name.startswith("Red") else "BLUE")
                index = self.RobotList.index(name) % 4
                x = max(-4.3, min(4.3, point[0]-direction*(.7+.25*index)))
                y = max(-2.7, min(2.7, point[1]+(-1 if index%2 else 1)*(.7+.25*index)))
                node.getField("translation").setSFVec3f([x, y, .334])
                node.getField("rotation").setSFRotation([0, 0, 1, 0 if direction == 1 else math.pi])
                node.resetPhysics()
                node.restartController()

    def enforce_incapable_players(self):
        now = self.getTime()
        for name, node in self.robots.items():
            team = "RED" if name.startswith("Red") else "BLUE"
            direction = self.match.direction(team)
            if name in self.penalties:
                if now >= self.penalties[name]:
                    del self.penalties[name]
                    index = self.RobotList.index(name)%4
                    node.getField("translation").setSFVec3f([-direction*(3-.6*index), 2.75, .334])
                    node.getField("rotation").setSFRotation([0, 0, 1, -math.pi/2])
                    node.resetPhysics()
                    node.restartController()
                    self.log_file.write(json.dumps({"event": "penalty_end", "robot": name, "time": now})+"\n")
                continue
            if self.match.phase != "PLAYING":
                self.fallen_since.pop(name, None)
                self.outside_since.pop(name, None)
                continue
            p = node.getPosition()
            fallen = node.getOrientation()[8] < .5
            outside = abs(p[0]) > 5.5 or abs(p[1]) > 4
            for condition, timers in ((fallen, self.fallen_since), (outside, self.outside_since)):
                if condition:
                    timers.setdefault(name, now)
                else:
                    timers.pop(name, None)
            reason = "fallen" if now-self.fallen_since.get(name, now) >= 20 else "outside" if now-self.outside_since.get(name, now) >= 20 else None
            if reason:
                self.remove_player(name, reason, now)

    def remove_player(self, name, reason, now):
        direction = self.match.direction("RED" if name.startswith("Red") else "BLUE")
        node = self.robots[name]
        self.penalties[name] = now+10
        index = self.RobotList.index(name)%4
        node.getField("translation").setSFVec3f([-direction*(3-.6*index), 3.5, .334])
        node.getField("rotation").setSFRotation([0, 0, 1, -math.pi/2])
        node.resetPhysics()
        node.restartController()
        self.fallen_since.pop(name, None)
        self.outside_since.pop(name, None)
        self.log_file.write(json.dumps({"event": "penalty", "reason": reason, "robot": name, "time": now})+"\n")

    def enforce_restart_positions(self, previous_phase):
        now = self.getTime()
        if self.match.phase == "SET" and previous_phase == "READY":
            for name, node in self.robots.items():
                team = "RED" if name.startswith("Red") else "BLUE"
                direction = self.match.direction(team)
                p = node.getPosition()
                in_wrong_half = direction*p[0] > 0
                protected_circle = self.match.restart == "DROP_BALL" or team != self.match.restart_team
                in_circle = protected_circle and math.hypot(p[0], p[1]) < .75
                if name not in self.penalties and (in_wrong_half or in_circle):
                    # Illegal kickoff placement has no removal time penalty in HL 2025.
                    # Put the player on its own touch line; it may autonomously enter at PLAY.
                    index = self.RobotList.index(name)%4
                    node.getField("translation").setSFVec3f([-direction*(3.8-.8*index), -3.35, .334])
                    node.getField("rotation").setSFRotation([0, 0, 1, math.pi/2])
                    node.resetPhysics()
                    node.restartController()
                    self.log_file.write(json.dumps({"event": "setup_removal", "robot": name, "time": now})+"\n")
        elif self.match.phase == "PLAYING" and previous_phase == "PREPARE":
            ball = self.ball.getPosition()
            for name, node in self.robots.items():
                team = "RED" if name.startswith("Red") else "BLUE"
                if team != self.match.restart_team and name not in self.penalties and math.dist(node.getPosition()[:2], ball[:2]) < .75:
                    self.remove_player(name, "restart_distance", now)

    def updateMatch(self):
        previous_phase = self.match.phase
        events = self.match.step(self.getTime(), list(self.ball.getPosition()), self.physical_touch())
        for event in events:
            self.log_file.write(json.dumps(event)+"\n")
            if event["event"] == "phase":
                print(f'MATCH: {event["phase"]} half={self.match.half}', flush=True)
            elif event["event"] == "goal":
                print(f'{event["team"]} GOAL!', flush=True)
            elif event["event"] == "place_ball":
                self.place_restart_ball(event["point"])
        self.enforce_restart_positions(previous_phase)
        self.enforce_incapable_players()
        self.setLabel(6, f'{self.match.phase}  H{self.match.half}  {self.match.snapshot()["remaining"]:.0f}s',
                      .35, .015, .035, 0x222222, 0, "Arial")

    def resetSimulation(self):
        # Preserve match score/time, restore saved poses and clear player state.
        self.ball.loadState("kickoff")
        self.ball.resetPhysics()
        self.previousBallLocation = [0, 0, BALL_RADIUS]
        self.previousGoalSample = [0, 0, BALL_RADIUS]
        for robot in self.robots.values():
            robot.loadState("kickoff")
            robot.resetPhysics()
            robot.restartController()
