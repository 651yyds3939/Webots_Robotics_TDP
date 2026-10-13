"""Shared Webots execution adapter for the eight fixed-role players.

No Supervisor methods are available here: locomotion is exclusively joint
motion playback. Referee broadcasts are a declared localization source.
"""
import configparser
import json
import math
import os
from pathlib import Path
import tempfile
from controller import Robot, Motion
from Utils.ProcessSupervisor import SupervisorData
from Utils.TeamPolicy import TeamPolicy
from Utils.HeadingFilter import HeadingFilter
from Utils.Navigation import Navigator

MOTION_FILES = {
    "stand": "StandInit.motion", "walk": "ForwardLoop.motion",
    "back": "Backwards.motion", "step_left": "SideStepLeftLoop.motion", "step_right": "SideStepRightLoop.motion",
    "dribble": "Forwards50.motion", "sprint": "ForwardsSprint.motion",
    "shoot": "Shoot.motion", "pass": "LongPass.motion",
    "left10": "TurnLeft10.motion", "left20": "TurnLeft20.motion", "left40": "TurnLeft40.motion",
    "left60": "TurnLeft60.motion", "left180": "TurnLeft180.motion",
    "right10": "TurnRight10.motion", "right20": "TurnRight20.motion", "right40": "TurnRight40.motion",
    "right60": "TurnRight60.motion",
    "recover_front": "StandUpFromFront.motion", "recover_back": "StandUpFromBack.motion",
}


class MotionLibrary:
    """Filter unsupported motion channels without changing the source assets."""
    def __init__(self, robot):
        self.devices = {robot.getDeviceByIndex(i).getName(): robot.getDeviceByIndex(i) for i in range(robot.getNumberOfDevices())}
        self.directory = tempfile.TemporaryDirectory(prefix="tdp-motion-")
        self.loaded = {}
        self.audit = {}

    def get(self, action):
        if action == "stand":
            # Rebuild the transition from the current commanded posture on every stop.
            self.loaded.pop(action, None)
        if action not in self.loaded:
            source = Path(__file__).resolve().parents[2] / "motions" / MOTION_FILES[action]
            rows = [line.strip().split(",") for line in source.read_text().splitlines() if line.strip()]
            indices = [i for i, name in enumerate(rows[0]) if i < 2 or name in self.devices]
            audit = {"removed_channels": [name for name in rows[0][2:] if name not in self.devices], "clipped_samples": 0}
            # Respect the actual model limits instead of sending out-of-range angles.
            for i in indices[2:]:
                motor = self.devices[rows[0][i]]
                if not hasattr(motor, "getMinPosition"):
                    continue
                low, high = motor.getMinPosition(), motor.getMaxPosition()
                if high > low:
                    for row in rows[1:]:
                        if row[i] != "*":
                            old = float(row[i])
                            new = max(low, min(high, old))
                            audit["clipped_samples"] += int(new != old)
                            row[i] = str(new)
            if action == "stand":
                # Initial stance must not jump from straight legs in a single 40 ms frame.
                first = list(rows[1])
                first[0] = "00:00:000"
                for i in indices[2:]:
                    first[i] = str(self.devices[rows[0][i]].getTargetPosition())
                rows[-1][0] = "00:01:000"
                rows.insert(1, first)
            path = Path(self.directory.name) / MOTION_FILES[action]
            path.write_text("\n".join(",".join(row[i] for i in indices) for row in rows)+"\n")
            self.loaded[action] = Motion(str(path))
            self.audit[action] = audit
        return self.loaded[action]


class SoccerController:
    def __init__(self):
        self.robot = Robot()
        self.name = self.robot.getName()
        self.time_step = int(self.robot.getBasicTimeStep())
        self.policy = TeamPolicy(self.name)
        self.observation = SupervisorData(self.name)
        self.receiver = self.robot.getDevice("receiver")
        self.receiver.enable(self.time_step)
        self.emitter = self.robot.getDevice("emitter")
        self.pass_intent = None
        self.imu = self.robot.getDevice("inertial unit")
        self.imu.enable(self.time_step)
        self.library = MotionLibrary(self.robot)
        self.current = None
        self.current_action = ""
        self.current_behaviour = ""
        self.heading = HeadingFilter()
        self.navigator = Navigator()
        self.navigation_stage = ''
        self.action_started = 0
        settings = configparser.ConfigParser()
        settings.read(Path(__file__).resolve().parents[1] / "Utils/globalconfig.ini")
        self.source = settings.get("Controller", "Observation", fallback="supervisor")
        if self.source not in ("supervisor", "vision"):
            raise ValueError("Observation must be supervisor or vision")
        self.sprint = settings.getboolean("Controller", "Sprint", fallback=False)
        self.vision = None
        self.camera = None
        if self.source == "vision":
            from Utils.ImageServer import ImageServer
            self.camera = self.robot.getDevice("CameraBottom")
            self.camera.enable(4*self.time_step)
            self.vision = ImageServer(self.camera.getWidth(), self.camera.getHeight(), self.camera, self.name,
                                      "Bottom", display=settings.getboolean("Controller", "DisplayVision", fallback=False))
            self.head_yaw = self.robot.getDevice("HeadYawS")
            self.head_pitch = self.robot.getDevice("HeadPitchS")
            self.head_yaw.enable(self.time_step)
            self.head_pitch.enable(self.time_step)
        directory = Path(os.environ.get("TDP_RUN_DIR", str(Path(__file__).resolve().parents[3] / "runs")))
        directory.mkdir(parents=True, exist_ok=True)
        self.log = (directory / f"player-{self.name}-{os.getpid()}.jsonl").open("w", buffering=1)
        self.play("stand", "INITIALIZE")

    def play(self, action, behaviour):
        if action == "stand" and self.current_action == "stand" and self.current and self.current.isOver():
            return
        if self.current and not self.current.isOver():
            if action == self.current_action:
                return
            if self.current_action.startswith("recover") and behaviour not in ("WAIT", "PENALIZED", "STALE_DATA"):
                return
            # Complete turns, kicks and recovery before switching normal actions.
            if (self.current_action not in ("walk", "sprint", "stand")
                    and not action.startswith("recover") and behaviour not in ("WAIT", "PENALIZED", "BALL_LOST", "STALE_DATA")):
                return
            self.current.stop()
        self.current = self.library.get(action)
        self.current.setLoop(action == "walk")
        self.current.play()
        self.current_action = action
        self.action_started = self.robot.getTime()
        self.log.write(json.dumps({"event": "command", "robot": self.name, "time": self.robot.getTime(),
                                   "action": action, "behaviour": behaviour, "source": self.source,
                                   "motion_preparation": self.library.audit[action]})+"\n")
        return True

    def receive(self):
        while self.receiver.getQueueLength():
            message = self.receiver.getString()
            try:
                packet = json.loads(message)
            except (ValueError, TypeError):
                packet = None
            if isinstance(packet, dict) and packet.get("kind") == "pass_intent":
                try:
                    sender, receiver = packet["sender"], packet["receiver"]
                    expires = packet["expires"]
                    valid = (sender in self.observation.robot_list and receiver in self.observation.robot_list
                             and sender != receiver and sender.startswith(self.policy.prefix)
                             and receiver.startswith(self.policy.prefix) and isinstance(expires, (int, float))
                             and math.isfinite(expires) and self.robot.getTime() <= expires <= self.robot.getTime()+25)
                    if valid:
                        self.pass_intent = packet
                        self.log.write(json.dumps({"event": "pass_intent_received", "robot": self.name,
                                                   "time": self.robot.getTime(), "sender": sender, "receiver": receiver})+"\n")
                except (KeyError, TypeError, ValueError):
                    pass
                finally:
                    self.receiver.nextPacket()
            else:
                self.observation.updateData(self.receiver)

    def visual_world(self, world):
        """Hybrid experiment: camera ball estimates, declared referee localization.

        Fixed-camera extrinsics follow NaoV6.proto. Projection assumes an upright
        torso; this mode needs physical camera calibration before hardware use.
        Ball loss stops movement and never falls back silently to referee ball data.
        """
        own = world["robots"][self.name]
        image = self.camera.getImage()
        metadata = {"time": self.robot.getTime(), "pose": own, "head_yaw": self.head_yaw.getValue(),
                    "head_pitch": self.head_pitch.getValue()}
        if image:
            self.vision.send(image, metadata)
        detection = self.vision.latest()
        if not detection or self.robot.getTime()-detection["capture"]["time"] > .8:
            return None
        from Utils.VisionGeometry import ball_world_position
        estimate = ball_world_position(detection)
        # A copy prevents modifying the referee evidence held by SupervisorData.
        result = {**world, "ball": {"position": estimate, "velocity": [0, 0, 0]}}
        self.log.write(json.dumps({"event": "vision", "robot": self.name, "time": self.robot.getTime(),
                                   "estimated_ball": estimate, "reference_ball": world["ball"]["position"]})+"\n")
        return result

    def act(self, world):
        if self.robot.getTime()-world["time"] > .4:
            self.play("stand", "STALE_DATA")
            return
        if world["match"]["phase"] in ("INITIAL", "SET", "STOPPED", "HALFTIME", "FINISHED") or self.name in world["penalties"]:
            self.pass_intent = None
            self.play("stand", "WAIT" if self.name not in world["penalties"] else "PENALIZED")
            return
        roll, pitch, yaw = self.imu.getRollPitchYaw()
        if self.robot.getTime() < 1.2:
            return
        if not all(math.isfinite(v) for v in (roll, pitch, yaw)):
            self.play("stand", "STALE_DATA")
            return
        if abs(pitch) > .8 or abs(roll) > .8:
            self.play("recover_front" if pitch > 0 else "recover_back", "RECOVER")
            return
        yaw = self.heading.update(yaw, self.robot.getTime())
        if self.source == "vision" and world["match"]["phase"] == "PLAYING":
            world = self.visual_world(world)
            if world is None:
                self.play("stand", "BALL_LOST")
                return
        if self.pass_intent:
            if self.pass_intent["expires"] <= self.robot.getTime() or world["match"]["last_touch"] == self.pass_intent["receiver"]:
                self.pass_intent = None
            else:
                world = {**world, "pass_intent": self.pass_intent}
        decision = self.policy.decide(world)
        if decision.behaviour != self.current_behaviour:
            if decision.behaviour == "RECEIVE_PASS" and self.current_action.startswith(("left", "right")):
                self.current.stop()
                self.current = None
            self.current_behaviour = decision.behaviour
            self.log.write(json.dumps({"event": "decision", "robot": self.name, "time": self.robot.getTime(),
                                      **decision.__dict__})+"\n")
        if decision.behaviour in ("WAIT", "PENALIZED"):
            self.play("stand", decision.behaviour)
            return
        own = world['robots'][self.name]['position']
        ball = world['ball']['position']
        action, stage = self.navigator.choose(decision, own, yaw, ball,
                                             [r['position'] for n, r in world['robots'].items() if n != self.name])
        if stage != self.navigation_stage:
            self.navigation_stage = stage
            self.log.write(json.dumps({'event': 'navigation', 'robot': self.name, 'time': self.robot.getTime(),
                                       'stage': stage, 'behaviour': decision.behaviour,
                                       'position': own, 'ball': ball, 'yaw': yaw, 'action': action})+'\n')
        # Preserve a complete walking cycle. Safety/phase/recovery checks above
        # still stop it immediately; ordinary tracking does not restart every half-step.
        if (self.current_action == 'walk' and self.current and not self.current.isOver()
                and self.robot.getTime()-self.action_started < .96 and action != 'walk'):
            return
        if action in ('shoot', 'pass') and self.current_action not in ('stand', 'shoot', 'pass'):
            self.play('stand', 'SETTLE_BEFORE_KICK')
            return
        if action in ('shoot', 'pass') and self.current_action == 'stand' and not self.current.isOver():
            return
        started = self.play(action, decision.behaviour)
        if started and action in ('shoot', 'pass') and decision.receiver:
            self.pass_intent = {'kind': 'pass_intent', 'sender': self.name,
                                'receiver': decision.receiver, 'expires': self.robot.getTime()+24}
            self.emitter.send(json.dumps(self.pass_intent).encode('utf-8'))

    def run(self):
        try:
            while self.robot.step(self.time_step) != -1:
                self.receive()
                if self.observation.world:
                    self.act(self.observation.world)
        finally:
            if self.vision:
                self.vision.stop()
            self.log.close()
            self.library.directory.cleanup()


def main():
    SoccerController().run()
