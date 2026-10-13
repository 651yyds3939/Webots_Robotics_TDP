"""Validated observations. V2 JSON replaces mixed untyped player status packets."""
import json
import math

ROBOT_NAMES = ["RedGoalkeeper", "RedDefender", "RedForwardB", "RedForwardA",
               "BlueGoalkeeper", "BlueDefender", "BlueForwardB", "BlueForwardA"]


def vector(value, length):
    if not isinstance(value, list) or len(value) != length:
        raise ValueError("Invalid vector length")
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in value):
        raise ValueError("Non-finite coordinate")
    return value


def validate_world(world):
    if world.get("version") != 2:
        raise ValueError("Unsupported observation version")
    vector(world["ball"]["position"], 3)
    vector(world["ball"]["velocity"], 3)
    if not math.isfinite(world["time"]):
        raise ValueError("Invalid timestamp")
    for name in ROBOT_NAMES:
        vector(world["robots"][name]["position"], 3)
        if not math.isfinite(world["robots"][name]["yaw"]):
            raise ValueError("Invalid yaw")
    match = world["match"]
    if match["phase"] not in {"INITIAL", "READY", "SET", "PLAYING", "STOPPED", "PREPARE", "HALFTIME", "FINISHED"}:
        raise ValueError("Invalid phase")
    if match["red_direction"] not in (-1, 1) or not isinstance(match["released"], bool):
        raise ValueError("Invalid direction/release flag")
    if match["half"] not in (1, 2) or not math.isfinite(match["remaining"]) or match["remaining"] < 0:
        raise ValueError("Invalid match clock")
    vector(match["score"], 2)
    if not all(isinstance(v, int) and v >= 0 for v in match["score"]):
        raise ValueError("Invalid score")
    vector(match["restart_point"], 3)
    if match["restart_team"] not in (None, "RED", "BLUE"):
        raise ValueError("Invalid restart team")
    if not set(world.get("penalties", {})).issubset(ROBOT_NAMES):
        raise ValueError("Invalid penalized player")
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in world.get("penalties", {}).values()):
        raise ValueError("Invalid penalty timer")
    return world


class SupervisorData:
    def __init__(self, robotName):
        self.robotName = robotName
        self.robot_list = ROBOT_NAMES
        self.world = None
        self.rejected_packets = 0
        self.data = {"msgID": 0, "ballPriority": "", "ballOwner": "",
                     "ballPosition": [0, 0, 0], "GameStatus": 0,
                     **{name: [0, 0, 0] for name in ROBOT_NAMES}}

    def updateData(self, receiver):
        message = receiver.getString()
        receiver.nextPacket()
        try:
            if isinstance(message, bytes):
                message = message.decode("utf-8")
            if message.startswith("{"):
                world = validate_world(json.loads(message))
                if self.world and world["time"] < self.world["time"]:
                    raise ValueError("Stale observation")
                self.world = world
                self.data.update({"GameStatus": int(world["match"]["phase"] == "PLAYING"),
                                  "ballPosition": world["ball"]["position"],
                                  "ballOwner": world.get("ball_owner", ""),
                                  **{name: world["robots"][name]["position"] for name in ROBOT_NAMES}})
            else:
                values = message.split(",")
                if values[0] == "1" and len(values) == 20:
                    coordinates = [float(v) for v in values[2:]]
                    if not all(math.isfinite(v) for v in coordinates):
                        raise ValueError("Invalid legacy coordinates")
                    self.data.update({"ballOwner": values[1], "ballPosition": coordinates[:2],
                                      **{name: coordinates[2+i*2:4+i*2] for i, name in enumerate(ROBOT_NAMES)}})
                elif values[0] == "2" and len(values) == 2 and values[1] in ("0", "1"):
                    # Legacy diagnostic only; V2 match state always belongs to the referee.
                    if self.world is None:
                        self.data["GameStatus"] = int(values[1])
                else:
                    raise ValueError("Invalid legacy packet")
            return True
        except (ValueError, KeyError, TypeError, OverflowError, AttributeError):
            self.rejected_packets += 1
            return False

    def getBallData(self):
        return self.data["ballPosition"]

    def getBallOwner(self):
        return self.data["ballOwner"].strip("*")

    def getBallPriority(self):
        return self.data["ballPriority"]

    def getSelfPosition(self):
        return self.data[self.robotName][:2]
